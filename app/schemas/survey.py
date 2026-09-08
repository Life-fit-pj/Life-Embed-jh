# Last Updated: 2026-09-08
"""설문 채점 API 요청·응답 모양. app/features/survey.py 와 1:1."""

from pydantic import BaseModel


class SurveyScoreRequest(BaseModel):
    prompt: str


class SurveyScoreOut(BaseModel):
    result: str
