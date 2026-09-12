"""search_graph 의 노드 3개다.

search_service.search() 에서 하던 일을 그대로 옮겼다.
각 노드는 SearchState 일부를 읽어 계산하고, 바뀐 부분만 dict 로 돌려준다 —
LangGraph 가 돌려받은 키만 기존 state 에 덮어쓴다.
"""

from app.ai.llm import ask, ask_with_tools
from app.core.config import INDICATORS
from app.engine.explain import explain, find_cases
from app.engine.weights import ask_claude, blend, find_similar_members
from app.repositories.members import member_weights
from app.services.chat_service import PLAN_SYSTEM, SYSTEM_PROMPT, build_context
from app.services.search_service import recommend_by_weights
from app.tools.tools import TOOL_SPECS, run_tool


# 검색어 -> 가중치 + 가격 조건
def weights_node(state):
    draft, persona_query = ask_claude(state["query"])
    similar = find_similar_members(persona_query)
    ids = [cid for cid, _ in similar]
    weights = blend(draft, member_weights(ids))

    weights_override = state["weights_override"]
    if weights_override:
        weights = {**weights,
                   **{k: float(v) for k, v in weights_override.items() if k in INDICATORS}}

    housing = state["housing_override"]
    if housing is None and draft.get("건물유형") and draft.get("거래유형") and draft.get("예산"):
        targets = {"예산": draft["예산"]}
        if draft["거래유형"] == "월세" and draft.get("보증금"):
            targets["보증금"] = draft["보증금"]
        housing = {"건물유형": draft["건물유형"], "거래유형": draft["거래유형"], "targets": targets}

    return {
        "draft": draft,
        "persona_query": persona_query,
        "weights": weights,
        "housing": housing,
        "path": state["path"] + ["weights"],
    }


# 가중치 -> TOP 5
def recommend_node(state):
    regions = recommend_by_weights(state["weights"], top_k=state["top_k"], housing=state["housing"])
    return {"regions": regions, "path": state["path"] + ["recommend"]}


# TOP 5 -> 설명문
def explain_node(state):
    cases = find_cases(state["persona_query"])
    text = explain(state["query"], state["weights"], state["regions"], cases, housing=state["housing"])
    return {"cases": cases, "explanation": text, "path": state["path"] + ["explain"]}

# 질문 -> 도구를 쓸지, 기존 방식(context 통째로)으로 답할지
def chat_plan_node(state):
    names = [r.get("name", "").replace("서울특별시 ", "") for r in state["regions"] or []]
    user_prompt = f"추천된 동네: {', '.join(names)}\n\n질문: {state['question']}"
    calls = ask_with_tools([("system", PLAN_SYSTEM), ("human", user_prompt)], TOOL_SPECS)

    if not calls:
        return {"route": "context", "tool_calls": [], "path": state["path"] + ["plan"]}
    return {"route": "tool", "tool_calls": calls, "path": state["path"] + ["plan"]}


# plan 이 고른 도구를 실제로 실행한다
def chat_run_tools_node(state):
    results = [run_tool(call["name"], call["arguments"]) for call in state["tool_calls"]]
    return {"tool_result": results, "path": state["path"] + ["run_tools"]}


# 질문 + 추천 결과 -> Claude 에게 넘길 재료 글 (route == "context" 일 때만 돈다)
def chat_context_node(state):
    context = build_context(state["regions"], state["weights"], state["question"])
    return {"context": context, "path": state["path"] + ["context"]}


# 재료 글(또는 도구 조회 결과) -> 답변
def chat_generate_node(state):
    if state["route"] == "tool":
        user_prompt = f"질문: {state['question']}\n\n조회 결과: {state['tool_result']}"
    else:
        user_prompt = f"{state['context']}\n\n## 질문\n{state['question']}"

    messages = [("system", SYSTEM_PROMPT), ("human", user_prompt)]
    answer = ask(messages, max_tokens=600).strip()
    return {"answer": answer, "path": state["path"] + ["generate"]}

