# Last Updated: 2026-09-08
"""동네 시설/설명 API 요청·응답 모양. app/features/regions.py·region_explain.py 와 1:1."""

from pydantic import BaseModel

from app.schemas.recommend import Housing


class FacilityItem(BaseModel):
    name: str
    category: str | None = None


class FacilitiesOut(BaseModel):
    counts: dict[str, int]
    items: dict[str, list[FacilityItem]]
    extras: dict   # region_extras() 가 내는 칸이 늘어날 수 있어 느슨하게 둔다


class RegionExplainRequest(BaseModel):
    query: str = ""
    weights: dict[str, float] | None = None
    scores: dict[str, int] | None = None
    housing: Housing | None = None


class RegionExplainOut(BaseModel):
    explanation: str
