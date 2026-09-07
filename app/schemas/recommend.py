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


class RecommendRequest(BaseModel):
    weights: dict[str, float]
    top_k: int = 5
    housing: Housing | None = None


class RecommendExplainedRequest(BaseModel):
    weights: dict[str, float]
    persona_query: str
    top_k: int = 5
    housing: Housing | None = None


class RegionOut(BaseModel):
    name: str
    total: float
    scores: dict[str, int]
    price: dict | None = None


class SearchOut(BaseModel):
    query: str
    persona_query: str
    weights: dict[str, float]
    regions: list[RegionOut]
    explanation: str
    housing: Housing | None = None


class RecommendExplainedOut(BaseModel):
    weights: dict[str, float]
    regions: list[RegionOut]
    explanation: str
    housing: Housing | None = None
