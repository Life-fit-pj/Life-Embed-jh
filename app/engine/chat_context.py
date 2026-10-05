"""후속 질문(채팅)에서 Claude 에게 넘길 재료 글.

graph 의 채팅 노드가 쓴다. 프롬프트는 app/prompts/chat.py 에 있다 — 거기서 "시세" 항목 · "생활여건" 항목이라고
가리키는 줄을 여기서 만든다. 줄의 머리를 바꾸면 프롬프트도 같이 본다(tests/test_prompts.py 가 지킨다).

재료는 동네 하나를 설명하는 region_service 와 같다 — 지표 점수와 실제 시설 개수.
다른 점은 추천된 다섯 곳을 전부 싣는다는 것이다. 질문이 어느 동네에 대한 것인지 미리 알 수 없다.
"""

from app.engine.housing import PRICE_LINE_COLUMNS, price_lines
from app.repositories.regions import region_bundle


# 재료로 읽는 master 의 칸 — 시세 줄을 만드는 칸들과 생활여건 셋
CONTEXT_COLUMNS = (*PRICE_LINE_COLUMNS, "소음_주간_구", "소음_야간_구", "거주안정성_점수")
TOP_CATEGORIES = 6      # 시설 종류마다 싣는 분류 수


def _place(r):
    """추천된 동네 하나의 (구, 동). 이름이 "구 동" 꼴이 아니면 None"""
    parts = r.get("name", "").replace("서울특별시 ", "").split(" ", 1)
    return tuple(parts) if len(parts) == 2 else None


def _region_block(r, bundle):
    """추천된 동네 하나의 재료 줄들. DB 는 안 읽는다 — build_context 가 다섯 곳 것을 한 번에 읽어 bundle 로 넘긴다"""
    lines = []
    name = r.get("name", "").replace("서울특별시 ", "")
    scores = r.get("scores") or {}
    score_text = " / ".join(f"{k} {round(v)}" for k, v in scores.items())
    lines.append(f"{r.get('rank', '?')}위 {name} (종합 {r.get('score')})")
    lines.append(f"     {score_text}")

    place = _place(r)
    if place is None:
        return lines

    kinds = bundle["facilities"].get(place, {})      # {종류: {분류: 개수}}. 한 곳도 없는 종류는 안 들어 있다
    if kinds:
        text = " · ".join(f"{kind} {sum(cats.values())}곳" for kind, cats in kinds.items())
        lines.append(f"     시설: {text}")

        # 분류별 개수도 넣는다.
        # "영어학원 많아?" 같은 질문은 개수만으로는 답할 수 없다.
        # 표본이 아니라 전체를 센 값이라 숫자를 그대로 써도 된다
        for kind, cats in kinds.items():
            top = sorted(((c, n) for c, n in cats.items() if c is not None), key=lambda item: (-item[1], item[0]))
            if len(top) > 1:
                cat_text = " · ".join(f"{c} {n}" for c, n in top[:TOP_CATEGORIES])
                lines.append(f"       {kind} 분류: {cat_text}")

    row = bundle["rows"].get(place)
    if row is None:
        return lines

    price = price_lines(row, bundle["prices"].get(place, {}))
    if price:
        lines.append("     시세 (동네 전체 중앙값, 실제 매물가 아님):")
        for pl in price:
            lines.append(f"       {pl}")

    noise = row.get("소음_주간_구"), row.get("소음_야간_구")
    if any(v is not None for v in noise):
        lines.append(
            f"     생활여건({place[0]} 구 단위 평균): 소음 주간 {noise[0]} · 야간 {noise[1]}"
            + (f" · 거주안정성 {row['거주안정성_점수']}점"
               if row.get("거주안정성_점수") is not None else "")
        )

    return lines


def build_context(regions, weights):
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
    # 다섯 곳의 재료를 한 번에 읽는다 — 표마다 한 번씩 여덟 번이다.
    # 동네마다 · 시설 종류마다 따로 읽으면 83번 왕복이다(2026-10-05 실측 4.4초). 그것도 동시에 보내서 그만큼이고,
    # 차례로 읽던 때는 35초가 걸려 웹의 30초 한도를 넘겼다(2026-10-01)
    places = [place for place in map(_place, regions or []) if place]
    bundle = region_bundle(places, CONTEXT_COLUMNS)
    for r in regions or []:
        lines.extend(_region_block(r, bundle))

    return "\n".join(lines)
