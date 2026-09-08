# Last Updated: 2026-09-08
"""좋아요·기록 창구. app/api가 부르는 문."""

from app.repositories.history import (
    add_chat_history, add_like, add_search_history,
    list_chat_history, list_search_history, remove_like,
)


def get_history(anon_id):
    """검색·대화 기록 조회. 최근 순."""
    return {
        "searches": list_search_history(anon_id),
        "chats": list_chat_history(anon_id),
    }


__all__ = [
    "add_like", "remove_like",
    "add_search_history", "add_chat_history",
    "get_history",
]
