"""search_graph 가 들고 다니는 상태다.

search_service.search() 의 지역 변수들을 그대로 옮겨 담았다 —
draft/persona_query 는 weights.ask_claude(), weights 는 blend(),
housing 은 검색어(또는 화면)에서 뽑힌 가격 조건, regions 는 TOP 5,
cases 는 유사 사례, explanation 은 최종 설명문이다.
"""

from typing import TypedDict


class SearchState(TypedDict):
    # 요청 입력 — search() 의 인자를 그대로 받는다
    query: str
    top_k: int
    housing_override: dict | None
    weights_override: dict | None

    # weights 노드가 채운다: Claude 초안 + 검색용 문장
    draft: dict
    persona_query: str

    # weights 노드가 채운다: 회원 보정까지 끝난 최종 가중치
    weights: dict

    # weights 노드가 채운다: 검색어(또는 화면)에서 뽑힌 가격 조건. 없으면 None
    housing: dict | None

    # recommend 노드가 채운다: TOP 5 (지표 점수 포함)
    regions: list

    # explain 노드가 채운다: 유사 사례
    cases: list

    # explain 노드가 채운다: 최종 설명문
    explanation: str

    # 어떤 노드를 거쳤는지. 디버깅용
    path: list
