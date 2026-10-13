# Last Updated: 2026-09-08
"""후속 질문 라우트 + 장기 메모리 조회·삭제."""

from fastapi import APIRouter, BackgroundTasks

from app.services.chat_service import chat, forget, read_memory, remember
from app.schemas.chat import ChatOut, ChatRequest, MemoryOut

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
def post_chat(body: ChatRequest, background: BackgroundTasks):
    """추천 결과에 대한 후속 질문에 답한다. 답을 돌려준 뒤 질문에서 거주 선호를 뽑아 기억한다(회원만)."""
    answer = chat(body.question, regions=body.regions, weights=body.weights, history=body.history,
                  anon_id=body.anon_id)
    background.add_task(remember, body.anon_id, body.question)
    return {"answer": answer}


@router.get("/memory/{customer_id}", response_model=MemoryOut | None)
def get_memory_route(customer_id: str):
    """채팅에서 기억한 거주 선호. 없으면 null."""
    return read_memory(customer_id)


@router.delete("/memory/{customer_id}")
def delete_memory_route(customer_id: str):
    """기억한 선호를 모두 지운다."""
    forget(customer_id)
    return {"ok": True}
