"""추천 엔드포인트 둘.

  POST /recommend           검색어 -> 가중치 + TOP 5 + 설명문   (LLM 을 부른다)
  POST /recommend/weights   가중치 -> TOP 5                   (LLM 을 안 부른다)

요청이 흘러가는 길 —
  여기 -> app/services/search_service.py -> app/engine/ · app/rag/ -> app/tables/ -> DB

Life-Web/routers/recommend.py 의 /predict 가 하던 일과 같다.
다른 점은 화면용 변환(영문 키 -> 한글 지표, 좌표 붙이기)이 없다는 것 —
그건 화면의 사정이므로 팀원이 옮겨 올 때 같이 온다.
"""

from fastapi import APIRouter

from app.schemas.recommend_schema import SearchRequest, SearchResponse, WeightsRequest, RegionOut
from app.services import search_service

router = APIRouter(prefix="/recommend", tags=["추천"])


@router.post("", response_model=SearchResponse)
def recommend_by_query(request: SearchRequest):
    """검색어 한 줄로 추천받는다."""
    return search_service.search(request.query, top_k=request.top_k)


@router.post("/weights", response_model=list[RegionOut])
def recommend_by_weights(request: WeightsRequest):
    """가중치를 직접 줘서 추천받는다. 골든 `recommend.json` 이 보는 길이다."""
    return search_service.recommend_by_weights(request.weights, top_k=request.top_k)
