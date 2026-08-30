"""
할 일 : 추천 결과에 대한 후속 질문에 답한다

region_explain.py 는 동네 하나를 설명하고 끝난다.
이 파일은 사용자가 이어서 묻는 것에 답한다.

재료는 같다 — 지표 점수와 실제 시설 목록.
다른 점은 "무엇을 물었는지" 에 따라 필요한 동네만 골라 온다는 것이다.
"""

from app.core.db import facilities, facility_counts, facility_categories, region_extras
from app.core.llm import get_llm
from pipeline.housing import region_price_lines

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

   소음처럼 "생활여건" 항목은 구(자치구) 단위 평균입니다. 그 동네만의 값인 것처럼 말하지 말고
   반드시 "OO구 평균으로는"이라고 밝히세요.

4. 다른 동네를 새로 추천해 달라고 하면, 지금은 그 기능이 없다고 알리고
   왼쪽 슬라이더를 조절하거나 다시 검색해 달라고 안내하세요.

5. 답은 3~4문장으로 짧게. 목록이 필요하면 최대 5개까지만.

존댓말로 답하세요."""


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
    for r in regions or []:
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

    return "\n".join(lines)


def chat(question, regions=None, weights=None, history=None):
    """후속 질문에 답한다.

    history 는 지금은 안 쓰지만 자리를 열어 둔다 —
    나중에 로그인·대화 저장을 붙이면 DB 에서 불러와 넘기게 된다
    """
    context = build_context(regions, weights, question)

    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"{context}\n\n## 질문\n{question}"),
    ]
    return get_llm(max_tokens=600).invoke(messages).content.strip()