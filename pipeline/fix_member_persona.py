"""
회원 페르소나 정상화 — customers 표와 chunks 의 인물이 다른 문제를 고친다.

원인 (지금은 pipeline/chunk.py 의 load_members 가 그 규칙을 갖고 있다):
  nemotron.csv 는 customer_id 가 없어 "customers.csv 와 순서로 맞춘다"는
  규칙으로 앞 100줄에 C001~C100 을 순서대로 붙였다. 그런데 customers 표
  (customers_v2.csv)는 별도로 다시 생성되어 순서가 어긋났다 — C001·C002 는
  우연히 이름까지 맞았지만(둘 다 nemotron.csv 1·2번째 줄과 동일 인물),
  C003부터는 완전히 다른 사람 얘기다. 100명 중 98명이 이름부터 불일치.

원본 매핑을 되돌릴 방법이 없으므로(어느 쪽이 "먼저"인지 알 수 없다),
customers 표 — 실제 서울 행정동 주소를 쓰고 추천 엔진이 그대로 참조하는
쪽 — 를 기준으로 페르소나 9칸을 그 사람 정보에 맞게 다시 쓴다.
이미 이름이 맞는 회원은 건드리지 않는다(재실행해도 안전).

⚠ 되돌릴 방법이 없다. 청크와 벡터를 지우고 새로 쓰는데, DB 가 파일이 아니라
  Supabase 라서 "백업 파일을 복사해 둔다" 가 안 된다. 되돌리려면 chunks 를
  pipeline.chunk -> pipeline.embed 로 통째로 다시 만들어야 한다(OpenAI 요금이 다시 나간다).
  먼저 몇 명만 시험해 보고 싶으면 fix_all() 의 targets 를 잘라서 돌린다.
"""

import json
import re
import time

from app.ai.llm import ask
from app.core.config import CHUNK_COLUMNS
from app.db import SessionLocal
from app.engine.resync import resync_member
from app.models.chunk import Chunk
from app.models.customer import Customer

LABELS = {
    "persona": "총괄 요약 (이 사람이 어떤 사람인지 2~3문장)",
    "professional_persona": "직업 — 무슨 일을 하고 일터에서 어떤 모습인지",
    "sports_persona": "운동 — 즐기는 신체 활동이나 그 이유",
    "arts_persona": "예술·취미 — 여가를 보내는 방식",
    "travel_persona": "여행 — 선호하는 여행 스타일",
    "culinary_persona": "음식 — 식사 습관과 좋아하는 음식",
    "family_persona": "가족 — 가족 구성과 그 안에서의 역할",
    "cultural_background": "문화 배경 — 자란 환경이 지금 가치관에 남긴 흔적",
    "career_goals_and_ambitions": "커리어 목표 — 일에 대해 바라는 것",
}


CUSTOMER_FIELDS = ("customer_id", "name", "gender", "age",
                   "city", "city_dong", "work_city", "work_dong")


def _mismatched_customers(db):
    """persona 청크의 이름이 실제 회원 이름과 다른 사람만 골라낸다.

    회원 100명에 조회가 101번 나간다(회원 목록 1 + 사람마다 1). 로컬 파일일 때는
    공짜였지만 Postgres 는 네트워크 왕복이다 — 그래서 persona 청크를 한 번에
    받아 딕셔너리로 만들어 두고 맞춰 본다
    """
    customers = [
        dict(zip(CUSTOMER_FIELDS, row))
        for row in db.query(*[getattr(Customer, f) for f in CUSTOMER_FIELDS])
        .order_by(Customer.customer_id)
        .all()
    ]

    personas = dict(
        db.query(Chunk.source_id, Chunk.text)
        .filter(Chunk.source == "member", Chunk.category == "persona")
        .all()
    )

    return [
        c for c in customers
        if not personas.get(c["customer_id"], "").startswith(c["name"])
    ]


def _build_prompt(customer: dict) -> str:
    fields = "\n".join(f"- {key} ({label})" for key, label in LABELS.items())
    gender = "남성" if customer["gender"] == "M" else "여성"
    return f"""아래 인물의 라이프스타일 페르소나를 9개 항목으로 써라.

인물 정보:
- 이름: {customer['name']}
- 성별: {gender}, 나이: {customer['age']}세
- 거주지: {customer['city']} {customer['city_dong']}
- 직장 위치: {customer['work_city']} {customer['work_dong']}

규칙:
- 모든 항목은 "{customer['name']} 씨는 ~"으로 시작하는 한국어 문장 1~3개.
- 문장은 "~합니다/~입니다"체로 끝낼 것(반말·개조식 금지).
- 위 인물 정보(나이·거주지·직장 위치)와 어긋나는 내용을 쓰지 말 것.
- 항목마다 30자 이상 쓸 것.
- 직업·취미·가족 구성 등 정보에 없는 세부사항은 자연스럽게 지어내되,
  나이·성별·거주지와 모순되지 않게 할 것.
- 설명 없이 JSON 객체 하나만 출력하라. 키는 다음 9개를 정확히 써라:
{fields}
"""


def _parse(raw: str) -> dict | None:
    t = re.sub(r"```(?:json)?|```", "", str(raw)).strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not all(k in data and len(str(data[k]).strip()) >= 20 for k in CHUNK_COLUMNS):
        return None
    return {k: str(data[k]).strip() for k in CHUNK_COLUMNS}


def fix_all():
    # 대상을 먼저 다 뽑고 세션을 닫는다. 뒤 반복문은 LLM 을 기다리며 몇 분씩 도는데,
    # 그동안 세션을 붙들고 있으면 연결만 잡아먹는다(resync_member 가 자기 세션을 연다)
    db = SessionLocal()
    try:
        targets = _mismatched_customers(db)
    finally:
        db.close()

    print(f"고칠 회원 {len(targets)}명")

    fixed, failed = 0, []

    for i, customer in enumerate(targets, start=1):
        prompt = _build_prompt(customer)
        persona = None
        for attempt in range(2):          # 한 번 실패하면 한 번만 더 시도
            raw = ask(prompt, max_tokens=1200)
            persona = _parse(raw)
            if persona:
                break
            time.sleep(1)

        if persona is None:
            failed.append(customer["customer_id"])
            print(f"  [{i}/{len(targets)}] {customer['customer_id']} 실패 — JSON 파싱/검증 안 됨")
            continue

        row = {**persona, "customer_id": customer["customer_id"]}
        resync_member(customer["customer_id"], row)
        fixed += 1
        print(f"  [{i}/{len(targets)}] {customer['customer_id']} ({customer['name']}) 완료")

    print(f"✅ {fixed}명 정상화, 실패 {len(failed)}명: {failed}")


if __name__ == "__main__":
    fix_all()
