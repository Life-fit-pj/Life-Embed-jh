"""
할 일 : 추천 결과에 대한 후속 질문에 답한다

region_service.py 는 동네 하나를 설명하고 끝난다.
이 파일은 사용자가 이어서 묻는 것에 답한다.

재료는 같다 — 지표 점수와 실제 시설 목록.
다른 점은 "무엇을 물었는지" 에 따라 필요한 동네만 골라 온다는 것이다.
"""

from concurrent.futures import ThreadPoolExecutor

from app.repositories.regions import facility_counts, facility_categories, region_extras
from app.engine.housing import region_price_lines

SYSTEM_PROMPT = """당신은 주거지 추천 서비스 LIFE,FIT 의 상담 도우미입니다.
사용자는 방금 동네 추천을 받았고, 그에 대해 이어서 묻고 있습니다.

## 반드시 지킬 것

1. 주어진 데이터에 있는 숫자와 시설 이름만 쓰세요. 지어내지 마세요.

2. 점수는 서울 427개 행정동 중 백분위입니다. 98점 = 상위 2% 입니다.

3. 데이터에 없는 것을 물으면 없다고 답하세요.
   없는 것: 관리비, 교육비, 통학 시간, 지하철 노선명, 학군 배정, 시설의 품질이나 평판, 주민 성향
   지역에 대한 통념(강남은 비싸다 등)도 쓰지 마세요.

   시세(매매가·보증금·월세)는 아래 "시세" 항목에 준 값만 쓰세요 — 동네 전체 중앙값이지
   실제 매물 가격이 아니라는 점을 밝히세요. 사용자가 특정 조건(예: "월세")을 물으면 그 항목만
   골라 답하세요.
   금액 뒤 괄호의 신뢰등급·거래건수·분포도 물어보면 답하세요 — 거래건수가 적거나 신뢰등급이
   낮으면 표본이 적어 참고용이라고 밝히세요.
   
   "시세" 점수는 다른 지표와 방향이 반대입니다 — 값이 클수록 그 동네 시세가
   서울에서 낮은(저렴한) 편이라는 뜻입니다. "시세 85점"은 "저렴한 쪽 상위 15%"이지
   "비싸다"가 아닙니다.
   "시세" 항목의 금액은 준 그대로 쓰세요. 단위를 바꾸거나 다시 계산하지 마세요.

   소음처럼 "생활여건" 항목은 구(자치구) 단위 평균입니다. 그 동네만의 값인 것처럼 말하지 말고
   반드시 "OO구 평균으로는"이라고 밝히세요.

4. 조회 결과에 "순위"가 있으면, 그것은 사용자가 말한 기준으로 서울 전체를 다시 줄 세운 새 TOP 5 입니다.
   순위대로 알려 주고, 무엇을 기준으로 봤는지("기준")와 반영하지 못한 것("안_반영된_것")을 한 문장으로 밝히세요.
   화면의 지도와 목록은 바뀌지 않습니다 — 화면에도 반영하려면 그 말로 다시 검색해 달라고 안내하세요.
   조회 결과에 "오류"가 있으면 그 기준으로는 다시 볼 수 없다고 알리고, 고를 수 있는 것을 알려 주세요.

   그 밖에 다른 동네를 새로 추천해 달라고 하면(조회 결과에 순위가 없으면), 지금은 그 기능이 없다고 알리고
   왼쪽 슬라이더를 조절하거나 다시 검색해 달라고 안내하세요.

5. 답은 3~4문장으로 짧게. 목록이 필요하면 최대 5개까지만.

존댓말로 답하세요."""


PLAN_SYSTEM = """추천된 동네에 대한 후속 질문입니다. 아래 도구로 답할 수 있는
구체적인 질문(시설 개수·분류, 시세, 소음·가구 구성 같은 생활 여건)이면 도구를 고르세요.
두 동네 이상을 비교하는 질문이면 동네마다 같은 도구를 하나씩 부르세요.
추천 기준을 좁혀 다시 보고 싶다는 질문("학원 많은 쪽으로 다시 보면?", "지하철 기준으로는 어디야?")이면
rerank_by_focus 를 고르세요 — 지표 하나와 그 안의 한 가지를 짝으로 고릅니다. 맞는 짝이 없으면 고르지 마세요.
점수의 의미나 왜 추천됐는지처럼 도구로 답할 수 없는 질문이면 도구를 고르지 마세요."""


def _region_block(r):
    """추천된 동네 하나의 재료 줄들. DB 조회가 전부 여기 모여 있다 — build_context 가 동네마다 스레드로 부른다"""
    lines = []
    name = r.get("name", "").replace("서울특별시 ", "")
    scores = r.get("scores") or {}
    score_text = " / ".join(f"{k} {round(v)}" for k, v in scores.items())
    lines.append(f"{r.get('rank', '?')}위 {name} (종합 {r.get('score')})")
    lines.append(f"     {score_text}")

    parts = name.split(" ", 1)
    if len(parts) == 2:
        gu, dong = parts
        counts = facility_counts(gu, dong)
        if counts:
            text = " · ".join(f"{k} {n}곳" for k, n in counts.items())
            lines.append(f"     시설: {text}")

            # 분류별 개수도 넣는다.
            # "영어학원 많아?" 같은 질문은 개수만으로는 답할 수 없다.
            # facilities() 의 표본이 아니라 전체를 센 값이라 숫자를 그대로 써도 된다
            for kind in counts:
                cats = facility_categories(gu, dong, kind, top=6)
                if len(cats) > 1:
                    cat_text = " · ".join(f"{c['category']} {c['n']}" for c in cats)
                    lines.append(f"       {kind} 분류: {cat_text}")

        price_lines = region_price_lines(gu, dong)
        if price_lines:
            lines.append("     시세 (동네 전체 중앙값, 실제 매물가 아님):")
            for pl in price_lines:
                lines.append(f"       {pl}")

        extras = region_extras(gu, dong)
        noise = extras.get("소음_주간_구"), extras.get("소음_야간_구")
        if any(v is not None for v in noise):
            lines.append(
                f"     생활여건({gu} 구 단위 평균): 소음 주간 {noise[0]} · 야간 {noise[1]}"
                + (f" · 거주안정성 {extras['거주안정성_점수']}점"
                   if extras.get("거주안정성_점수") is not None else "")
            )

    return lines


def build_context(regions, weights, question):
    """Claude 에게 넘길 재료를 글로 정리한다.

    추천된 5개 동네의 지표와 시설을 모두 넣는다.
    질문이 어느 동네에 대한 것인지 미리 알 수 없기 때문이다
    """
    lines = []

    high = [k for k, w in (weights or {}).items() if w >= 3.5]
    high_text = ", ".join(high) if high else "뚜렷한 편중 없음"
    lines.append(f"## 사용자가 중시한 항목\n{high_text}")
    lines.append("")

    lines.append("## 추천된 동네 (점수는 서울 427개 동 중 백분위)")
    # 동네마다 조회가 20번이 넘고 원격 DB 라 건당 0.3초다. 차례로 하면 5곳에 35초 — 웹의 30초 한도를 넘어
    # 500 이 됐다(2026-10-01 실측). 동시에 보내 가장 느린 한 곳만큼만 기다린다.
    # map 은 넣은 순서대로 돌려주므로 1위~5위 순서는 그대로다
    with ThreadPoolExecutor(max_workers=5) as pool:
        for block in pool.map(_region_block, regions or []):
            lines.extend(block)

    return "\n".join(lines)


# 앞선 대화는 최근 몇 턴만 싣는다. 브라우저가 보내는 값이라 길이를 여기서 자른다 —
# 안 자르면 아주 긴 기록 하나로 토큰 비용을 마음대로 늘릴 수 있다
HISTORY_TURNS = 6
HISTORY_CHARS = 1000


def history_messages(history):
    """[{"role": "user"|"assistant", "content": 글}] -> llm.ask 가 받는 튜플 목록."""
    turns = []
    for item in (history or [])[-HISTORY_TURNS:]:
        text = str(item.get("content") or "")[:HISTORY_CHARS]
        if text:
            turns.append(("ai" if item.get("role") == "assistant" else "human", text))
    # Claude API 는 대화가 사용자 말로 시작해야 한다 — 잘라낸 앞머리가 답이면 버린다
    while turns and turns[0][0] == "ai":
        turns.pop(0)
    return turns


def chat(question, regions=None, weights=None, history=None):
    """후속 질문에 답한다.

    실제 계산은 app/graph/graph.py 의 chat_graph 가 한다 —
    plan 이 도구를 쓸지(tool) 기존 방식대로 답할지(context) 정하고 generate 로 합류한다.

    history 는 같은 추천 결과를 두고 앞서 주고받은 말이다 — "거기", "그럼 두 번째 동네는?"
    처럼 앞 질문을 가리키는 말을 알아듣게 plan·generate 둘 다에 싣는다
    """
    from app.graph.graph import chat_graph

    state = {
        "question": question,
        "regions": regions or [],
        "weights": weights or {},
        "history": history_messages(history),
        "route": "",
        "tool_calls": [],
        "tool_result": [],
        "context": "",
        "answer": "",
        "path": [],
    }
    result = chat_graph.invoke(state)
    return result["answer"]