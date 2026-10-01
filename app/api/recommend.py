# Last Updated: 2026-09-07
"""추천 라우트. app/features/search.py 창구를 그대로 부른다."""

from fastapi import APIRouter

from app.features.search import focus_options, recommend_by_weights, recommend_by_weights_explained, search
from app.schemas.recommend import (
    RecommendExplainedRequest, RecommendExplainedOut,
    RecommendRequest, RegionOut,
    SearchRequest, SearchOut,
)

router = APIRouter(tags=["recommend"])


@router.post("/search", response_model=SearchOut)
def post_search(body: SearchRequest):
    """검색어 → 가중치 + TOP 5 + 설명문."""
    return search(
        body.query,
        top_k=body.top_k,
        housing_override=body.housing_override.model_dump() if body.housing_override else None,
        weights_override=body.weights_override,
        focus_override=body.focus_override,
    )


@router.post("/recommend", response_model=list[RegionOut])
def post_recommend(body: RecommendRequest):
    """가중치 → TOP 5."""
    return recommend_by_weights(
        body.weights,
        top_k=body.top_k,
        housing=body.housing.model_dump() if body.housing else None,
        focus=body.focus,
    )


@router.get("/recommend/focus-options", response_model=dict[str, list[str]])
def get_focus_options():
    """지표별로 콕 집을 수 있는 세부 목록. 화면이 칩을 그릴 때 쓴다 — {"교육": ["학원", "학교"], …}"""
    return focus_options()


@router.post("/recommend/explained", response_model=RecommendExplainedOut)
def post_recommend_explained(body: RecommendExplainedRequest):
    """가중치 + 사람 묘사 문장 → TOP 5 + 설명문."""
    return recommend_by_weights_explained(
        body.weights,
        body.persona_query,
        top_k=body.top_k,
        housing=body.housing.model_dump() if body.housing else None,
        focus=body.focus,
    )
