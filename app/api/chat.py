# Last Updated: 2026-09-08
"""후속 질문 라우트."""

from fastapi import APIRouter

from app.features.chat import chat
from app.schemas.chat import ChatOut, ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
def post_chat(body: ChatRequest):
    """추천 결과에 대한 후속 질문에 답한다."""
    answer = chat(body.question, regions=body.regions, weights=body.weights, history=body.history)
    return {"answer": answer}
