# Last Updated: 2026-09-08
"""관리자 분석 대화 라우트."""

from fastapi import APIRouter, HTTPException

from app.features.analysis import ask, delete_chat, get_chat, list_chats
from app.schemas.analysis import AnalysisChatListItem, AnalysisChatOut, AskOut, AskRequest, DeleteOut

router = APIRouter(prefix="/admin/analysis", tags=["admin-analysis"])


@router.post("/ask", response_model=AskOut)
def post_ask(body: AskRequest):
    """질문 하나에 답하고 기록에 남긴다. 질문이 비어 있으면 422."""
    result = ask(body.question)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.get("/chats", response_model=list[AnalysisChatListItem])
def get_chats(limit: int = 50):
    """저장된 분석 대화 목록."""
    return list_chats(limit)


@router.get("/chats/{chat_id}", response_model=AnalysisChatOut)
def get_chat_detail(chat_id: int):
    """대화 하나를 통째로. 없으면 404."""
    chat = get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="chat not found")
    return chat


@router.delete("/chats/{chat_id}", response_model=DeleteOut)
def delete_chat_route(chat_id: int):
    """대화 하나를 지운다."""
    return {"deleted": delete_chat(chat_id)}
