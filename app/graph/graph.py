"""노드들을 이어 붙여 그래프를 만든다.

search_graph — weights_node 가 housing_override/weights_override 를 이미
내부에서 다 처리하므로, 갈림길 없이 직선으로만 잇는다 — add_conditional_edges 는 안 쓴다.
chat_graph — plan 이 도구를 쓸지(tool) 기존 방식대로 답할지(context) 정하고,
그 갈림길만 add_conditional_edges 로 잇는다. 둘 다 generate 로 합류한다.
"""

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import ChatState, SearchState


# plan 이 정해 둔 값을 그대로 읽는다. "tool" 또는 "context"
def choose_chat_route(state):
    return state["route"]


def build_search_graph():
    builder = StateGraph(SearchState)

    builder.add_node("weights", nodes.weights_node)
    builder.add_node("recommend", nodes.recommend_node)
    builder.add_node("explain", nodes.explain_node)

    builder.add_edge(START, "weights")
    builder.add_edge("weights", "recommend")
    builder.add_edge("recommend", "explain")
    builder.add_edge("explain", END)

    return builder.compile()


def build_chat_graph():
    builder = StateGraph(ChatState)

    builder.add_node("plan", nodes.chat_plan_node)
    builder.add_node("run_tools", nodes.chat_run_tools_node)
    builder.add_node("context", nodes.chat_context_node)
    builder.add_node("generate", nodes.chat_generate_node)

    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", choose_chat_route, {"tool": "run_tools", "context": "context"})
    builder.add_edge("run_tools", "generate")
    builder.add_edge("context", "generate")
    builder.add_edge("generate", END)

    return builder.compile()


# 그래프는 한 번씩만 만들어 두고 계속 쓴다.
search_graph = build_search_graph()
chat_graph = build_chat_graph()
