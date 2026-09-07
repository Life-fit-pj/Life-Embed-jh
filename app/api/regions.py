# Last Updated: 2026-09-08
"""동네 시설/설명 라우트."""

from fastapi import APIRouter

from app.features.region_explain import region_explain_cached
from app.features.regions import get_facilities
from app.schemas.regions import FacilitiesOut, RegionExplainOut, RegionExplainRequest

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/{gu}/{dong}/facilities", response_model=FacilitiesOut)
def get_region_facilities(gu: str, dong: str, limit: int = 5):
    """행정동 하나의 시설 정보. 지도 핀을 눌렀을 때 쓴다."""
    return get_facilities(gu, dong, limit=limit)


@router.post("/{gu}/{dong}/explain", response_model=RegionExplainOut)
def post_region_explain(gu: str, dong: str, body: RegionExplainRequest):
    """동네 하나에 대한 LLM 설명."""
    housing = body.housing.model_dump() if body.housing else None
    explanation = region_explain_cached(
        gu, dong, query=body.query, weights=body.weights, scores=body.scores, housing=housing,
    )
    return {"explanation": explanation}
