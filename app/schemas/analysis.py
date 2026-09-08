# Last Updated: 2026-09-08
"""관리자 분석 API 요청·응답 모양. app/features/analysis.py 와 1:1."""

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class AskOut(BaseModel):
    chat_id: int
    question: str
    answer: str
    facts: dict


class AnalysisChatListItem(BaseModel):
    chat_id: int
    question: str
    preview: str
    created_at: str


class AnalysisChatOut(BaseModel):
    chat_id: int
    question: str
    answer: str
    facts: dict | None = None
    created_at: str


class DeleteOut(BaseModel):
    deleted: int
