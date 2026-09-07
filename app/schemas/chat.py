# Last Updated: 2026-09-08
"""후속 질문 API 요청·응답 모양. app/features/chat.py 와 1:1."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """지금 화면에 떠 있는 추천 결과(rank/score 등 화면용 필드 포함)를 그대로 받는다 —
    app/schemas/recommend.py의 RegionOut과 칸 이름이 달라 그 모델을 못 쓴다"""
    question: str
    regions: list[dict] | None = None
    weights: dict[str, float] | None = None
    history: list[dict] | None = None


class ChatOut(BaseModel):
    answer: str
