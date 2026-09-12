"""search_graph 의 노드 3개다.

search_service.search() 에서 하던 일을 그대로 옮겼다.
각 노드는 SearchState 일부를 읽어 계산하고, 바뀐 부분만 dict 로 돌려준다 —
LangGraph 가 돌려받은 키만 기존 state 에 덮어쓴다.
"""

from app.ai.llm import ask
from app.core.config import INDICATORS
from app.engine.explain import explain, find_cases
from app.engine.weights import ask_claude, blend, find_similar_members
from app.repositories.members import member_weights
from app.services.chat_service import SYSTEM_PROMPT, build_context
from app.services.search_service import recommend_by_weights


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

# 질문 + 추천 결과 -> Claude 에게 넘길 재료 글
def chat_context_node(state):
    context = build_context(state["regions"], state["weights"], state["question"])
    return {"context": context, "path": state["path"] + ["context"]}


# 재료 글 -> 답변
def chat_generate_node(state):
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"{state['context']}\n\n## 질문\n{state['question']}"),
    ]
    answer = ask(messages, max_tokens=600).strip()
    return {"answer": answer, "path": state["path"] + ["generate"]}

