# Last Updated: 2026-09-08
"""좋아요·기록 API 요청·응답 모양. app/features/history.py 와 1:1."""

from typing import Literal

from pydantic import BaseModel


class LikeRequest(BaseModel):
    anon_id: str
    gu: str
    dong: str


class HistoryEntryIn(BaseModel):
    anon_id: str
    kind: Literal["search", "chat"]
    query: str | None = None       # kind="search" 일 때만
    question: str | None = None    # kind="chat" 일 때만
    answer: str | None = None      # kind="chat" 일 때만


class SearchHistoryItem(BaseModel):
    query: str
    created_at: str


class ChatHistoryItem(BaseModel):
    question: str
    answer: str
    created_at: str


class HistoryOut(BaseModel):
    searches: list[SearchHistoryItem]
    chats: list[ChatHistoryItem]


class LikeItem(BaseModel):
    gu: str
    dong: str
    created_at: str
