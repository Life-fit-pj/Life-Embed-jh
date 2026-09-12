"""
검색어 하나로 전체 파이프라인을 돌리는 통합 창구.

이 파일에는 로직이 없다. weights → recommend → explain 을
순서대로 부르기만 한다. 서버(find-home 의 core.py)는
이 파일의 search() 하나만 알면 된다.

무거운 준비물(벡터·점수)은 처음 부를 때 한 번만 만든다.
서버는 요청마다 함수를 부르므로, 매번 만들면 요청 하나에 몇 초씩 걸린다.
"""

import numpy as np

from app.engine.explain import explain, find_cases, with_scores
from app.engine.recommend import (
    load_regions, build_scores, build_relative, recommend,
    PRICE_COLUMNS, load_price_values, build_price_score,
)
from app.engine.housing import matching_regions, attach_price

from app.repositories.regions import region_densities


# ── 준비물 보관함 ──────────────────────────────
_ready = None


def get_ready():
    """행정동 점수 등 무거운 준비물. 처음 한 번만 만든다.

    벡터는 여기 없다 — app/ai/vector_store.py 가 자기 캐시를 들고,
    청크가 바뀌면 스스로 버린다(7-8절)
    """
    global _ready
    if _ready is None:
        print("⏳ 파이프라인 준비 중...")

        names, values = load_regions()
        scores = build_scores(values)
        relative = build_relative(scores)

        price_values = load_price_values(region_densities(PRICE_COLUMNS))
        price_score = build_price_score(price_values)   # 427개 동, 0~100 — housing 없을 때만 쓴다

        _ready = {
            "names": names,
            "scores": scores,
            "relative": relative,
            "price_score": price_score,
        }
        print(f"✅ 준비 완료 · 행정동 {len(names)}개")
    return _ready


DEFAULT_PRICE_WEIGHT = 3   # 다른 지표들의 "보통"과 같은 값. 굳이 저렴함을 강하게 밀지 않는다


def recommend_by_weights(weights, top_k=5, housing=None):
    """가중치 → TOP 5. housing 을 주면 그 조건에 맞는 동으로 먼저 추린다.

    housing 예시(전세): {"건물유형": "아파트", "거래유형": "전세", "targets": {"예산": 65000}}
    housing 예시(월세): {"건물유형": "아파트", "거래유형": "월세",
                       "targets": {"예산": 70, "보증금": 5000}}   (단위: 만원)
    """
    r = get_ready()
    names, scores, relative = r["names"], r["scores"], r["relative"]

    if housing:
        candidates = set(matching_regions(**housing))
        keep = np.array([n in candidates for n in names])
        names = [n for n, k in zip(names, keep) if k]
        scores = {ind: arr[keep] for ind, arr in scores.items()}
        relative = {ind: arr[keep] for ind, arr in relative.items()}
    else:
        # 목표가가 없을 때만 "시세는 낮을수록 좋다"를 8번째 신호로 얹는다.
        # housing이 있으면 matching_regions()가 이미 목표가 근접도로 걸러내므로
        # 여기서 또 "무조건 저렴한 게 좋다"를 더하면 그 판단과 충돌한다.
        price = r["price_score"]
        scores = {**scores, "시세": price}
        # relative[k]는 recommend()에서 (relative[k]+50)으로 쓰이므로,
        # mix 값과 무관하게 결과가 항상 price_score 그대로 나오도록 -50을 맞춰 넣는다.
        relative = {**relative, "시세": price - 50}
        weights = {**weights, "시세": weights.get("시세", DEFAULT_PRICE_WEIGHT)}

    result = recommend(names, scores, relative, weights, top_k=top_k)
    detailed = with_scores(result, names, scores)
    return attach_price(detailed, housing)


def recommend_by_weights_explained(weights, persona_query, top_k=5, housing=None):
    """이미 계산된 가중치 + 사람 묘사 문장 -> TOP 5 + 설명문.

    search()와 달리 검색어를 안 받는다. 서술형 설문처럼 가중치를 이미
    직접 계산할 수 있을 때 쓴다 — ask_claude()(LLM 추정)와
    find_similar_members()/blend()(회원 유사도 보정) 두 단계를 건너뛰고
    recommend_by_weights() -> explain() 만 돈다.
    """
    r = get_ready()
    detailed = recommend_by_weights(weights, top_k=top_k, housing=housing)
    cases = find_cases(persona_query)
    text = explain(persona_query, weights, detailed, cases, housing=housing)
    return {
        "weights": weights,
        "regions": detailed,
        "explanation": text,
        "housing": housing,
    }

def search(query, top_k=5, housing_override=None, weights_override=None):
    """검색어 → 가중치 + TOP 5 + 설명문. 서버가 부르는 메인 창구.

    실제 계산은 app/graph/graph.py 의 search_graph 가 한다 —
    weights → recommend → explain 순서로 도는 3개 노드다(10단계).

    housing_override 를 주면 검색어에서 뽑아낸 가격 조건 대신 이 값을 그대로 쓴다 —
    화면에서 사용자가 이미 명시적으로 고른 조건(건물유형·거래유형·예산·보증금)이,
    검색어 문장에서 애매하게 뽑아낸 조건보다 신뢰도가 높다는 판단이다.

    weights_override 도 같은 취지다 — 1차 유형 카드가 이미 확정한 가중치가 있으면
    검색어에서 다시 추정하지 않고 그걸 쓴다. 이게 없으면 1차에서 보여 준 동네가
    2차 추천에서 통째로 사라진다(같은 문장을 다시 읽어 다른 가중치가 나오기 때문).
    """
    # app/graph/nodes.py 가 이 파일의 recommend_by_weights 를 가져다 쓰므로,
    # 파일 맨 위에서 바로 부르면 순환 참조로 임포트가 꼬인다. 부를 때만 가져온다
    from app.graph.graph import search_graph

    state = {
        "query": query,
        "top_k": top_k,
        "housing_override": housing_override,
        "weights_override": weights_override,
        "draft": {},
        "persona_query": "",
        "weights": {},
        "housing": None,
        "regions": [],
        "cases": [],
        "explanation": "",
        "path": [],
    }
    result = search_graph.invoke(state)

    return {
        "query": query,
        "persona_query": result["persona_query"],
        "weights": result["weights"],
        "regions": result["regions"],
        "explanation": result["explanation"],
        "housing": result["housing"],   # 검색어에서 뽑아낸(또는 화면에서 넘어온) 조건. 가격 언급이 없었으면 None
    }


if __name__ == "__main__" :
    import json
    
    result = search("얘들 학원 보내기 좋은 곳")
    
    print()
    print(f"가중치: {result['weights']}")
    print()
    for i, region in enumerate(result["regions"], start=1):
        print(f"{i}위 {region['name']} ({region['total']}점)")
    print()
    print(result["explanation"])
