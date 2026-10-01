# Last Updated: 2026-09-07
"""추천 API 요청/응답 모양. app/features/search.py 함수 셋(search·recommend_by_weights·
recommend_by_weights_explained)과 1:1."""

from pydantic import BaseModel


class Housing(BaseModel):
    건물유형: str
    거래유형: str
    targets: dict[str, float]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    housing_override: Housing | None = None
    weights_override: dict[str, float] | None = None
    # 화면의 칩이 고른 세부 {"교육": "학원"}. 있으면 검색어에서 뽑은 세부 대신 이걸 쓴다 — 누른 사람이 제일 확실하다
    focus_override: dict[str, str] | None = None


class RecommendRequest(BaseModel):
    weights: dict[str, float]
    top_k: int = 5
    housing: Housing | None = None
    # 세부 강조 {"교육": "학원"}. 화면의 칩이 채운다. 고를 수 있는 값은 GET /recommend/focus-options.
    # 없으면 지금까지와 똑같이 지표 평균으로 순위를 낸다
    focus: dict[str, str] | None = None


class RecommendExplainedRequest(BaseModel):
    weights: dict[str, float]
    persona_query: str
    top_k: int = 5
    housing: Housing | None = None
    focus: dict[str, str] | None = None


class RegionOut(BaseModel):
    name: str
    total: float
    scores: dict[str, int]
    counts: dict = {}
    price: dict | None = None


class SearchOut(BaseModel):
    query: str
    persona_query: str
    weights: dict[str, float]
    regions: list[RegionOut]
    explanation: str
    housing: Housing | None = None
    notice: str | None = None


class RecommendExplainedOut(BaseModel):
    weights: dict[str, float]
    regions: list[RegionOut]
    explanation: str
    housing: Housing | None = None
