# Last Updated: 2026-09-08
"""설문 라우트.

추천까지 필요하면 이 파일이 아니라 POST /recommend/explained를 부른다 —
설문 경로의 "추천"(옛 get_survey_recommendation)은 recommend_by_weights_explained를
그대로 부르는 것뿐이라 별도 엔드포인트를 두지 않는다.
"""

from fastapi import APIRouter

from app.features.survey import score_survey
from app.schemas.survey import SurveyScoreOut, SurveyScoreRequest

router = APIRouter(prefix="/survey", tags=["survey"])


@router.post("/score", response_model=SurveyScoreOut)
def post_survey_score(body: SurveyScoreRequest):
    """설문 프롬프트를 Claude에게 채점시킨다."""
    return {"result": score_survey(body.prompt)}
