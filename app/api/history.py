# Last Updated: 2026-09-08
"""좋아요·기록 라우트."""

from fastapi import APIRouter, HTTPException

from app.features.history import add_chat_history, add_like, add_search_history, get_history, remove_like
from app.schemas.history import HistoryEntryIn, HistoryOut, LikeRequest

router = APIRouter(tags=["history"])


@router.post("/likes")
def post_like(body: LikeRequest):
    """좋아요 추가. 이미 있으면 무시."""
    add_like(body.anon_id, body.gu, body.dong)
    return {"ok": True}


@router.delete("/likes")
def delete_like(body: LikeRequest):
    """좋아요 취소."""
    remove_like(body.anon_id, body.gu, body.dong)
    return {"ok": True}


@router.post("/history")
def post_history(body: HistoryEntryIn):
    """검색어 또는 채팅 한 건을 기록한다. kind로 어느 표에 쓸지 정한다."""
    if body.kind == "search":
        if body.query is None:
            raise HTTPException(status_code=422, detail="kind=search면 query가 있어야 한다")
        add_search_history(body.anon_id, body.query)
    else:
        if body.question is None or body.answer is None:
            raise HTTPException(status_code=422, detail="kind=chat이면 question과 answer가 있어야 한다")
        add_chat_history(body.anon_id, body.question, body.answer)
    return {"ok": True}


@router.get("/history/{anon_id}", response_model=HistoryOut)
def get_history_route(anon_id: str):
    """검색·대화 기록 조회."""
    return get_history(anon_id)
