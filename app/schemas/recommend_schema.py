"""추천 API 가 주고받는 형식.

지금까지 엔진은 dict 를 그대로 주고받았다. 형식을 여기 적어 두면
FastAPI 가 들어오는 값을 검사하고 /docs 를 만들어 준다(이론 11).

★ 요청은 못 박고 응답은 느슨하게 둔 이유 —
  요청은 우리가 정하는 것이라 지금 굳혀도 된다.
  응답의 regions 는 가격 조건에 따라 칸이 늘었다 줄었다 한다(attach_price).
  안 굳은 것을 굳은 척 적으면, 나중에 값이 하나 늘 때마다 422 가 난다.
"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """검색어 한 줄로 추천받는다. LLM 이 가중치를 추정한다."""

    query: str = Field(min_length=1, description="예: 애들 학원 보내기 좋은 곳")
    top_k: int = Field(default=5, ge=1, le=20)


class WeightsRequest(BaseModel):
    """가중치를 직접 줘서 추천받는다. LLM 을 안 부르므로 답이 항상 같다."""

    weights: dict[str, float] = Field(
        description='7지표. 예: {"녹지": 5, "안전": 5, "교통": 2, "상권": 2, '
                    '"의료": 4, "교육": 5, "문화": 1}'
    )
    top_k: int = Field(default=5, ge=1, le=20)


class RegionOut(BaseModel):
    """추천된 동네 하나."""

    name: str
    total: float
    scores: dict[str, int]

    # 가격 조건이 있으면 시세 칸이 더 붙는다(app/engine/housing.py 의 attach_price).
    # 그 모양이 아직 안 굳어서 통과시킨다. 굳으면 여기 적고 이 줄을 지운다
    model_config = {"extra": "allow"}


class SearchResponse(BaseModel):
    """검색어 추천의 답."""

    query: str
    persona_query: str          # 검색어를 "사람 묘사" 로 바꾼 문장
    weights: dict[str, float]   # blend() 가 항상 INDICATORS 7개만 돌려준다
    regions: list[RegionOut]
    explanation: str
    housing: dict | None        # 가격 언급이 없었으면 None

