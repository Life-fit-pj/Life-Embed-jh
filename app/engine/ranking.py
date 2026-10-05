"""가중치 → TOP 5. 순위 계산과 그 준비물.

검색(graph 의 recommend 노드) · 채팅 도구(tools.py) · 관리자 화면 · 추천 API 가 같이 쓴다.
services 와 graph 가 둘 다 필요로 하므로 둘보다 아래층인 여기에 둔다 — search_service 에 있을 때는
graph 가 services 를 거꾸로 불러 순환이 됐고, 함수 안 import 가 그것을 덮고 있었다(2026-10-05 에 옮김).

무거운 준비물(행정동 점수)은 처음 부를 때 한 번만 만든다.
서버는 요청마다 함수를 부르므로, 매번 만들면 요청 하나에 몇 초씩 걸린다.
"""

import numpy as np

from app.engine.explain import with_scores
from app.engine.housing import attach_price, matching_regions
from app.engine.recommend import (
    load_regions, build_scores, build_relative, recommend,
    build_column_scores, apply_focus, focus_scores,
    PRICE_COLUMNS, load_price_values, build_price_score,
)
from app.repositories.regions import region_densities


# ── 준비물 보관함 ──────────────────────────────
_ready = None


def get_ready():
    """행정동 점수 등 무거운 준비물. 처음 한 번만 만든다.

    벡터는 여기 없다 — app/ai/vector_store.py 가 DB 에 직접 묻는다
    """
    global _ready
    if _ready is None:
        print("⏳ 파이프라인 준비 중...")

        names, values, counts = load_regions()
        column_scores = build_column_scores(values)   # 칸별 백분위. 지표 점수의 재료이자 세부 강조가 꺼내 쓰는 값
        scores = build_scores(column_scores)
        relative = build_relative(scores)

        price_values = load_price_values(region_densities(PRICE_COLUMNS))
        price_score = build_price_score(price_values)
        
        _ready = {
            "names": names,
            "index": {name: i for i, name in enumerate(names)},     # "구 동" -> 자리 번호. 이름으로 동네를 찾는 곳들이 같이 쓴다
            "scores": scores,
            "relative": relative,
            "column_scores": column_scores,    # 칸별 백분위. 세부 강조(apply_focus)와 관리자 화면의 계산된 칸이 읽는다
            "price_score": price_score,
            "counts": counts,      # 화면 근거용 원본 개수. 순위 계산에는 안 쓴다
        }
        print(f"✅ 준비 완료 · 행정동 {len(names)}개")
    return _ready


def reset_ready():
    """준비물을 버린다. 다음에 get_ready() 를 부를 때 다시 만든다 — 행정동 값을 고쳤을 때 부른다.

    밖에서 `_ready = None` 을 직접 적지 않는다. 변수가 다른 파일로 옮겨 가면 그 줄은 에러 없이 빈 변수를 비운다
    """
    global _ready
    _ready = None


def is_ready():
    """준비물이 만들어져 있나. 관리자 화면의 상태 표시가 읽는다"""
    return _ready is not None


DEFAULT_PRICE_WEIGHT = 3   # 다른 지표들의 "보통"과 같은 값. 굳이 저렴함을 강하게 밀지 않는다


# 말로만 한 가격대("고급 아파트", "저렴한 곳")일 때 시세 신호의 가중치.
# 다른 지표의 최댓값(5)과 같게 둔다 — 사용자가 직접 말한 조건이기 때문이다
PRICE_TIER_WEIGHT = 5


def _keep(names, scores, relative, mask):
    """불리언 마스크로 names·scores·relative 를 같이 자른다 — 셋의 길이가 어긋나면 recommend() 가 죽는다"""
    names = [n for n, k in zip(names, mask) if k]
    scores = {ind: arr[mask] for ind, arr in scores.items()}
    relative = {ind: arr[mask] for ind, arr in relative.items()}
    return names, scores, relative


def recommend_by_weights(weights, top_k=5, housing=None, region=None, price_tier=None, focus=None):
    """가중치 → TOP 5. housing 을 주면 그 조건에 맞는 동으로 먼저 추린다.

    housing 예시(전세): {"건물유형": "아파트", "거래유형": "전세", "targets": {"예산": 65000}}
    housing 예시(월세): {"건물유형": "아파트", "거래유형": "월세",
                       "targets": {"예산": 70, "보증금": 5000}}   (단위: 만원)

    region 을 주면("강남구" 등) 그 구의 동으로만 다시 추린다. housing 필터와 별개로,
    항상 맨 마지막에 건다 — housing 이 없을 때 얹는 "시세" 8번째 신호(아래 else)까지
    427개 길이로 다 만들어진 뒤라야 배열 길이가 서로 맞는다.

    price_tier("고가"|"저가")는 금액 없이 말로만 한 가격대다. housing 이 없을 때만 쓴다.
    "시세" 점수는 클수록 저렴하므로, 고가면 순위 계산에만 뒤집은 값(100 - 점수)을 쓴다.
    화면·설명문으로 가는 점수(with_scores)는 원래 방향 그대로 둔다 — 뒤집힌 값이 나가면
    설명문이 "저렴하다"로 정반대로 읽는다.

    focus 를 주면({"교육": "학원"}) 순위를 매길 때 그 지표 점수를 콕 집은 칸의 백분위로 바꾼다.
    나가는 점수에는 지표 점수를 그대로 두고 "교육(학원)" 을 한 항목 더 싣는다. 맨 먼저 건다 —
    housing·region 이 배열을 자르기 전이라야 길이가 맞는다. 주는 곳은 둘 — 검색어에서 뽑힌 세부(weights 노드)와
    채팅의 rerank_by_focus 도구(app/tools/tools.py).
    """
    r = get_ready()
    names, scores, relative = r["names"], r["scores"], r["relative"]
    # 화면·설명문으로 나가는 점수. 427개 길이 그대로 둔다 — 아래에서 자르고 바꾸는 것은 전부 순위 계산용이다
    shown = dict(scores)

    if focus:
        # 세부 강조 — 순위는 그 지표를 평균 대신 콕 집은 칸의 백분위로 매긴다. 준비물은 복사해서 쓴다(apply_focus 가 새 dict).
        # 나가는 점수의 지표 값은 안 바꾼다 — 버스만 본 값을 "교통 99" 로 내보내면 설명문·화면이 뜻을 잘못 읽는다.
        # 대신 "교통(버스)" 를 한 항목 더 싣는다
        scores = apply_focus(scores, r["column_scores"], focus)
        relative = build_relative(scores)
        shown.update(focus_scores(r["column_scores"], focus))

    # scores·relative·rank_* 는 순위 계산에만 쓴다. rank_* 가 따로 있는 것은 가격대(고가)로 시세를 뒤집을 때 때문이다
    if housing:
        candidates = set(matching_regions(**housing))
        names, scores, relative = _keep(names, scores, relative, np.array([n in candidates for n in names]))
        rank_scores, rank_relative = scores, relative
    else:
        # 목표가가 없을 때만 "시세는 낮을수록 좋다"를 8번째 신호로 얹는다.
        # housing이 있으면 matching_regions()가 이미 목표가 근접도로 걸러내므로
        # 여기서 또 "무조건 저렴한 게 좋다"를 더하면 그 판단과 충돌한다.
        price = r["price_score"]
        shown["시세"] = price          # 나가는 값은 원래 방향 그대로다(클수록 저렴)
        scores = {**scores, "시세": price}
        # relative[k]는 recommend()에서 (relative[k]+50)으로 쓰이므로,
        # mix 값과 무관하게 결과가 항상 price_score 그대로 나오도록 -50을 맞춰 넣는다.
        relative = {**relative, "시세": price - 50}
        weights = {**weights, "시세": weights.get("시세", DEFAULT_PRICE_WEIGHT)}
        rank_scores, rank_relative = scores, relative
        if price_tier:
            rank_price = 100 - price if price_tier == "고가" else price
            rank_scores = {**scores, "시세": rank_price}
            rank_relative = {**relative, "시세": rank_price - 50}
            weights = {**weights, "시세": PRICE_TIER_WEIGHT}

    if region:
        # 이름은 "구 동" 형태다(load_regions() 참고) — 접두어로 그 구만 남긴다.
        # 매치가 하나도 없으면(Claude 가 없는 구를 지어낸 경우) 필터를 걸지 않고 넘어간다.
        keep = np.array([n.startswith(region + " ") for n in names])
        if keep.any():
            # rank_* 를 먼저 자른다 — _keep 이 names 를 바꾸기 전의 길이여야 마스크와 맞는다
            _, rank_scores, rank_relative = _keep(names, rank_scores, rank_relative, keep)
            names, scores, relative = _keep(names, scores, relative, keep)

    result = recommend(names, rank_scores, rank_relative, weights, top_k=top_k)
    detailed = with_scores(result, r["names"], shown, r["counts"])
    return attach_price(detailed, housing)
