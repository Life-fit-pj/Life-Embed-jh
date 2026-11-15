"""
할 일 : 추천 결과에 대한 후속 질문에 답한다

region_service.py 는 동네 하나를 설명하고 끝난다.
이 파일은 사용자가 이어서 묻는 것에 답한다.

프롬프트와 재료 글(build_context)은 app/engine/chat_context.py 에 있다 — graph 의 노드가 거기서 가져다 쓴다.
여기는 앞선 대화를 다듬고 chat_graph 를 돌리는 창구다.
"""

import re

from app.engine.memory import clean, extract, is_empty, merge, to_prompt_line
from app.graph.graph import chat_graph
from app.repositories.history import delete_memory, get_memory, save_memory


# 앞선 대화는 최근 몇 턴만 싣는다. 브라우저가 보내는 값이라 길이를 여기서 자른다 —
# 안 자르면 아주 긴 기록 하나로 토큰 비용을 마음대로 늘릴 수 있다
HISTORY_TURNS = 6
HISTORY_CHARS = 1000

# 장기 메모리는 회원만 남긴다 — 기기 번호(UUID)는 브라우저를 지우면 사라져 기억할 주인이 없다.
# Life-Web 의 state.js isLoggedIn() 과 같은 규칙이다
MEMBER_ID = re.compile(r"C\d+")


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

    돌려주는 memory 는 이번 답에 실은 기억 한 줄이다 — 화면이 말풍선 아래 "기억한 조건 반영" 으로 보여 준다
    """
    memory = to_prompt_line(get_memory(anon_id)) if _is_member(anon_id) else ""
    state = {
        "question": question,
        "regions": regions or [],
        "weights": weights or {},
        "history": history_messages(history),
        "anon_id": anon_id,
        "memory": memory,
        "route": "",
        "tool_calls": [],
        "tool_result": [],
        "context": "",
        "answer": "",
        "path": [],
    }
    result = chat_graph.invoke(state)
    return {"answer": result["answer"], "memory": memory}


def _is_member(anon_id):
    return bool(MEMBER_ID.fullmatch(anon_id or ""))


def remember(anon_id, question):
    """질문에서 거주 선호를 뽑아 기억에 합친다. 답을 돌려준 뒤 백그라운드로 돈다(app/api/chat.py).

    새로 말한 것이 없으면 DB 를 안 건드린다. 실패해도 채팅은 이미 끝났으므로 조용히 넘어간다 —
    기억은 덤이고, 기억 때문에 답이 늦거나 깨지면 안 된다
    """
    if not _is_member(anon_id):
        return
    try:
        new = extract(question)
        if not is_empty(new):
            save_memory(anon_id, merge(get_memory(anon_id), new))
    except Exception as e:                       # 백그라운드라 올려 봐야 받을 곳이 없다 — 로그만 남긴다
        print(f"[memory] {anon_id} 기억 실패: {type(e).__name__}: {e}")


def read_memory(customer_id):
    """마이페이지에 보여 줄 기억. 없으면 None"""
    return get_memory(customer_id)


def forget(customer_id, field=None, value=None):
    """field 가 없으면 모두 지운다(마이페이지). 있으면 그 칸만, 목록 칸은 value 하나만 지운다(채팅창 띠의 ✕).
    지우고 남은 게 없으면 줄째 지운다"""
    memory = get_memory(customer_id)
    if field is None or memory is None:
        delete_memory(customer_id)
        return
    if field in ("priorities", "avoid"):
        memory[field] = [v for v in memory[field] if v != value]
    elif field in ("budget_manwon", "deal_type", "commute"):
        memory[field] = None
    if is_empty(memory):
        delete_memory(customer_id)
    else:
        save_memory(customer_id, clean(memory))
