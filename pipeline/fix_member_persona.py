"""
회원 페르소나 정상화 — customers 표와 member_chunk 의 인물이 다른 문제를 고친다.

원인 (embed_member.py 주석 참고):
  nemotron.csv 는 customer_id 가 없어 "customers.csv 와 순서로 맞춘다"는
  규칙으로 앞 100줄에 C001~C100 을 순서대로 붙였다. 그런데 customers 표
  (customers_v2.csv)는 별도로 다시 생성되어 순서가 어긋났다 — C001·C002 는
  우연히 이름까지 맞았지만(둘 다 nemotron.csv 1·2번째 줄과 동일 인물),
  C003부터는 완전히 다른 사람 얘기다. 100명 중 98명이 이름부터 불일치.

원본 매핑을 되돌릴 방법이 없으므로(어느 쪽이 "먼저"인지 알 수 없다),
customers 표 — 실제 서울 행정동 주소를 쓰고 추천 엔진이 그대로 참조하는
쪽 — 를 기준으로 페르소나 9칸을 그 사람 정보에 맞게 다시 쓴다.
이미 이름이 맞는 회원은 건드리지 않는다(재실행해도 안전).

실행 전 반드시 data/life.db 를 백업해 둘 것 — 벡터까지 다시 만들어
덮어쓰므로 되돌리려면 백업 파일이 있어야 한다.
"""

import json
import re
import time

from app.core.config import CHUNK_COLUMNS
from app.core.db import get_con, dicts
from app.ai.llm import ask
from app.engine.resync import resync_member

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


def _mismatched_customers(con):
    """persona 청크의 이름이 실제 회원 이름과 다른 사람만 골라낸다."""
    customers = dicts(
        "SELECT customer_id, name, gender, age, city, city_dong, work_city, work_dong "
        "FROM customers ORDER BY customer_id"
    )
    out = []
    for c in customers:
        row = con.execute(
            "SELECT text FROM member_chunk WHERE customer_id = ? AND category = 'persona'",
            (c["customer_id"],),
        ).fetchone()
        if row is None or not row[0].startswith(c["name"]):
            out.append(c)
    return out


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
    con = get_con()
    targets = _mismatched_customers(con)
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
