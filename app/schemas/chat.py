# Last Updated: 2026-09-08
"""후속 질문 API 요청·응답 모양. app/services/chat_service.py 와 1:1."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """지금 화면에 떠 있는 추천 결과(rank/score 등 화면용 필드 포함)를 그대로 받는다 —
    app/schemas/recommend.py의 RegionOut과 칸 이름이 달라 그 모델을 못 쓴다"""
    question: str
    regions: list[dict] | None = None
    weights: dict[str, float] | None = None
    history: list[dict] | None = None
    anon_id: str | None = None      # 기기 번호. 로그인하면 회원 번호("C101"). 좋아요·닮은 회원 도구가 읽는다


class ChatOut(BaseModel):
    answer: str
    memory: str = ""        # 이번 답에 실은 기억 한 줄. 손님이거나 기억이 없으면 빈 글자


class MemoryOut(BaseModel):
    """채팅에서 기억한 거주 선호. app/engine/memory.py 의 칸과 같다"""
    budget_manwon: int | None = None
    deal_type: str | None = None
    commute: str | None = None
    priorities: list[str] = []
    avoid: list[str] = []
    updated_at: str | None = None
