"""
할 일 : 추천 결과에 대한 후속 질문에 답한다

region_service.py 는 동네 하나를 설명하고 끝난다.
이 파일은 사용자가 이어서 묻는 것에 답한다.

프롬프트와 재료 글(build_context)은 app/engine/chat_context.py 에 있다 — graph 의 노드가 거기서 가져다 쓴다.
여기는 앞선 대화를 다듬고 chat_graph 를 돌리는 창구다.
"""

from app.graph.graph import chat_graph


# 앞선 대화는 최근 몇 턴만 싣는다. 브라우저가 보내는 값이라 길이를 여기서 자른다 —
# 안 자르면 아주 긴 기록 하나로 토큰 비용을 마음대로 늘릴 수 있다
HISTORY_TURNS = 6
HISTORY_CHARS = 1000


def history_messages(history):
    """[{"role": "user"|"assistant", "content": 글}] -> llm.ask 가 받는 튜플 목록."""
    turns = []
    for item in (history or [])[-HISTORY_TURNS:]:
        text = str(item.get("content") or "")[:HISTORY_CHARS]
        if text:
            turns.append(("ai" if item.get("role") == "assistant" else "human", text))
    # Claude API 는 대화가 사용자 말로 시작해야 한다 — 잘라낸 앞머리가 답이면 버린다
    while turns and turns[0][0] == "ai":
        turns.pop(0)
    return turns


def chat(question, regions=None, weights=None, history=None, anon_id=None):
    """후속 질문에 답한다.

    실제 계산은 app/graph/graph.py 의 chat_graph 가 한다 —
    plan 이 도구를 쓸지(tool) 기존 방식대로 답할지(context) 정하고 generate 로 합류한다.

    history 는 같은 추천 결과를 두고 앞서 주고받은 말이다 — "거기", "그럼 두 번째 동네는?"
    처럼 앞 질문을 가리키는 말을 알아듣게 plan·generate 둘 다에 싣는다
    """
    state = {
        "question": question,
        "regions": regions or [],
        "weights": weights or {},
        "history": history_messages(history),
        "anon_id": anon_id,
        "route": "",
        "tool_calls": [],
        "tool_result": [],
        "context": "",
        "answer": "",
        "path": [],
    }
    result = chat_graph.invoke(state)
    return result["answer"]