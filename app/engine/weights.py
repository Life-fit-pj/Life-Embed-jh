# Last updated: 2026-09-08
"""
할 일 : 검색어를 가중치 7개로 바꾼다

[B] Claude 가 검색어를 읽고 초안을 만든다
[A] 비슷한 회원을 찾아 그들의 실제 가중치로 보정한다
"""

import json

from app.core.config import INDICATORS, SIMILARITY_FLOOR
from app.engine.recommend import SUB_COLUMNS
from app.prompts.search import WEIGHTS_PROMPT
from app.rag.retriever import retrieve_people
from app.repositories.members import customer_persona, member_weights
from app.ai.llm import ask


# Claude 초안과 회원 평균을 몇 대 몇으로 섞을지.
# 0.7 이면 Claude 70%, 회원 30%
CLAUDE_RATIO = 0.7


def indicator_weights(weights: dict | None) -> dict:
    """가중치에서 지표 7개만 뽑는다. 빠졌거나 비어 있는 지표는 보통(3)이다.

    채팅 상태의 가중치에는 시세 같은 다른 키가 섞여 온다 — 그대로 넘기면 recommend() 가 죽는다.
    회원의 선호도 행은 아예 없거나(None) 칸이 비어 있을 수 있다
    """
    return {k: float((weights or {}).get(k) or 3) for k in INDICATORS}


def find_similar_members(query, top_k=5):
    """검색어와 비슷한 회원 top_k 명.

    "사람별 최고 점수" 규칙은 vector_store.search_people 로 옮겼다 —
    kb 쪽 find_cases 와 달리 여기만 필요한 규칙이 아니었기 때문이다.

    반환 모양은 옛것 그대로다: [(customer_id, (점수, 칸이름, 글))]
    부르는 쪽(search.py 134행)이 [cid for cid, _ in similar] 로 쓴다
    """
    return [
        (customer_id, (score, row["category"], row["text"]))
        for customer_id, score, row in retrieve_people("member", query, top_k)
        if score >= SIMILARITY_FLOOR   # 안 비슷한 사람의 선호를 30% 섞지 않는다. 다 걸러지면 blend() 가 초안만 쓴다
    ]


def find_members_like(customer_id: str, top_k: int = 5):
    """이 회원과 페르소나가 닮은 회원들. 자기 자신은 뺀다. 페르소나가 없는 회원이면 None

    반환 모양은 find_similar_members 와 같다: [(customer_id, (점수, 칸이름, 글))]
    부르는 곳은 둘 — 관리자 화면(admin_service.similar_members)과 채팅 도구(tools.people_like_me)
    """
    persona = customer_persona(customer_id)
    if not persona:
        return None

    # persona 칸을 대표로 쓰고, 비어 있으면 있는 칸 아무거나 하나
    query = persona.get("persona") or next(iter(persona.values()), "")
    if not query:
        return []

    # 자기 자신이 반드시 1등으로 걸리므로 한 명 더 받아서 뺀다
    ranked = find_similar_members(query, top_k=top_k + 1)
    return [(cid, hit) for cid, hit in ranked if cid != customer_id][:top_k]


def ask_claude(query):
    """Claude 에게 가중치 초안과 검색용 문장을 받는다.

    돌려주는 것: (가중치 딕셔너리, 검색용 문장)

    검색용 문장이 왜 필요한가 —
    사용자 검색어는 "좋은 곳" 처럼 장소를 찾는 문장이다.
    그런데 chunks 표(source='member')에 담긴 건 사람을 묘사한 문장이다.
    성격이 다른 두 문장을 벡터로 비교하면 엉뚱한 게 걸린다.
    (실제로 "애들 학원 보내기 좋은 곳" 으로 검색하니
     교육 1점짜리 회원들이 뽑혔다. z = -0.94)
    그래서 검색 전에 사람 묘사로 바꿔서 성격을 맞춘다.
    """
    messages = [
        ("system", WEIGHTS_PROMPT),
        ("human", query),
    ]        
    text = ask(messages, max_tokens=300, temperature=0).strip()     # 같은 검색어엔 같은 가중치. 골든셋이 흔들리지 않게(2026-09-28)
    
        # 혹시 ```json 같은 게 붙어 나오면 떼어낸다
    text = text.replace("```json", "").replace("```","").strip()
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"[경고] JSON 파싱 실패: {text[:80]}")
        weights = {k: 3 for k in INDICATORS}            # 실패하면 전부 보통값
        weights.update({"건물유형": None, "거래유형": None, "예산": None, "보증금": None,
                        "지역": None, "미지원_조건": None, "가격대": None, "세부": None})
        return weights, query

    # 7개가 다 있는지, 1~5 범위인지 검사한다
    weights = {}
    for key in INDICATORS:
        value = data.get(key, 3)
        weights[key] = max(1, min(5, int(value)))

    # 문장이 없거나 비었으면 원래 검색어로 대체한다
    persona_query = (data.get("persona_query") or "").strip() or query

    # 가격 조건 — Claude 가 프롬프트를 안 지키고 다른 값을 줄 수도 있으니 한 번 더 검사한다.
    # pipeline/housing.py 의 DEAL_COLUMNS 키와 정확히 맞아야 하기 때문이다
    BUILDING_TYPES = {"단독다가구", "아파트", "연립다세대", "오피스텔"}
    DEAL_TYPES = {"매매", "전세", "월세"}

    건물유형 = data.get("건물유형")
    거래유형 = data.get("거래유형")

    weights["건물유형"] = 건물유형 if 건물유형 in BUILDING_TYPES else None
    weights["거래유형"] = 거래유형 if 거래유형 in DEAL_TYPES else None
    weights["예산"] = data.get("예산")
    weights["보증금"] = data.get("보증금")

    # 지역 — "구"로 안 끝나면 못 쓴다(recommend_by_weights()가 "이름 " 접두어로 거른다)
    지역 = (data.get("지역") or "").strip()
    weights["지역"] = 지역 if 지역.endswith("구") else None

    weights["미지원_조건"] = (data.get("미지원_조건") or "").strip() or None
    weights["가격대"] = data.get("가격대") if data.get("가격대") in ("고가", "저가") else None

    # 세부 강조 — SUB_COLUMNS 에 있는 이름만 통과시킨다. Claude 가 "보습학원"처럼 목록 밖을 주면 버린다
    focus = data.get("세부") or {}
    if not isinstance(focus, dict):     # "세부": "학원" 처럼 모양이 틀리면 버린다 — .items() 에서 요청 전체가 죽지 않게
        focus = {}
    weights["세부"] = {ind: sub for ind, sub in focus.items()
                     if isinstance(sub, str) and sub in SUB_COLUMNS.get(ind, {})} or None

    return weights, persona_query


# 초안이 이 값이면 "사용자가 언급하지 않은 지표"라는 뜻이다.
# 검색 프롬프트(WEIGHTS_PROMPT)의 규칙 1 ("말하지 않은 지표는 전부 3점")과 짝을 이룬다
NEUTRAL = 3


def blend(draft, members):
    """Claude 초안을 회원들의 실제 가중치로 보정한다.

    단, 사용자가 검색어에서 직접 말한 지표(초안이 NEUTRAL 이 아닌 것)는 보정하지 않는다.
    회원 100명 표본은 지표별 편향이 심해서(교육 평균 1.65 — 70명이 1점) 전부 보정하면
    사용자가 요구한 관심사가 오히려 깎이고, 말한 적 없는 상권·녹지가 올라온다.
    회원 평균은 "사용자가 말하지 않은 칸을 채우는" 용도로만 쓴다.

    돌려주는 것은 항상 INDICATORS 7개만이다 — draft 에 섞여 있는 가격 키
    (건물유형·거래유형·예산·보증금)는 recommend() 가 숫자로 취급해 터지므로 잘라낸다.
    """
    if not members:
        return {key: float(draft[key]) for key in INDICATORS}

    final = {}
    for key in INDICATORS:
        if draft[key] != NEUTRAL:
            final[key] = float(draft[key])      # 사용자가 말한 지표 — 초안을 지킨다
            continue

        # 비슷한 회원들의 평균
        values = [m[key] for m in members]
        member_avg = sum(values) / len(values)

        mixed = draft[key] * CLAUDE_RATIO + member_avg * (1 - CLAUDE_RATIO)
        final[key] = round(mixed, 1)

    return final



if __name__ == "__main__":
    for q in ["애들 학원 보내기 좋은 곳",
              "병원이 가깝고 할머니를 모시고 살기 좋은 곳",
              "멀지 않은 거리에 백화점이 있는 곳"]:
        print(f"검색어: {q}")

        draft, persona_query = ask_claude(q)
        print(f"   [B] Claude 초안 : {draft}")
        print(f"   [→] 검색용 문장 : {persona_query}")
        
        # 원래 검색어가 아니라 번역된 문장으로 검색한다
        similar = find_similar_members(persona_query)
        ids = [cid for cid, _ in similar]
        members = member_weights(ids)
        print(f"   [A] 유사 회원   : {ids}")

        final = blend(draft, members)
        print(f"   [최종] {final}")
        print()





