# Last Updated: 2026-09-08
"""좋아요·기록 창구. app/api가 부르는 문."""

from app.repositories.history import (
    add_chat_history, add_like, add_search_history,
    list_chat_history, list_likes as _list_likes, list_search_history, remove_like,
)


def get_history(anon_id):
    """검색·대화 기록 조회. 최근 순."""
    return {
        "searches": list_search_history(anon_id),
        "chats": list_chat_history(anon_id),
    }


def get_likes(anon_id):
    """좋아요한 동네 목록. 최근 순. 구/행정동명 -> gu/dong 으로 바꿔 준다(API 계약이 영문 키다)."""
    return [
        {"gu": r["구"], "dong": r["행정동명"], "created_at": r["created_at"]}
        for r in _list_likes(anon_id)
    ]


__all__ = [
    "add_like", "remove_like", "get_likes",
    "add_search_history", "add_chat_history",
    "get_history",
]
