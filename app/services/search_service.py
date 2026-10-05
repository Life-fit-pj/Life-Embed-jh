"""
검색어 하나로 전체 파이프라인을 돌리는 통합 창구.

이 파일에는 로직이 없다. weights → recommend → explain 을
순서대로 부르기만 한다. 서버(find-home 의 core.py)는
이 파일의 search() 하나만 알면 된다.

순위 계산과 그 준비물(get_ready · recommend_by_weights)은 app/engine/ranking.py 에 있다.
"""

from app.engine.explain import explain, find_cases
from app.engine.ranking import recommend_by_weights
from app.graph.graph import search_graph


def recommend_by_weights_explained(weights, persona_query, top_k=5, housing=None):
    """이미 계산된 가중치 + 사람 묘사 문장 -> TOP 5 + 설명문.

    search()와 달리 검색어를 안 받는다. 서술형 설문처럼 가중치를 이미
    직접 계산할 수 있을 때 쓴다 — ask_claude()(LLM 추정)와
    find_similar_members()/blend()(회원 유사도 보정) 두 단계를 건너뛰고
    recommend_by_weights() -> explain() 만 돈다.
    """
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
    state = {
        "query": query,
        "top_k": top_k,
        "housing_override": housing_override,
        "weights_override": weights_override,
        "draft": {},
        "persona_query": "",
        "weights": {},
        "housing": None,
        "region": None,
        "price_tier": None,
        "focus": None,
        "notice": None,
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
        "notice": result["notice"],     # 검색어가 요구했지만 데이터가 없어 못 담은 조건. 없으면 None
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
