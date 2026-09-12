"""노드 3개를 이어 붙여 그래프를 만든다.

weights_node 가 housing_override/weights_override 를 이미 내부에서
다 처리하므로, 갈림길 없이 직선으로만 잇는다 — add_conditional_edges 는 안 쓴다.
"""

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import SearchState


def build_graph():
    builder = StateGraph(SearchState)

    builder.add_node("weights", nodes.weights_node)
    builder.add_node("recommend", nodes.recommend_node)
    builder.add_node("explain", nodes.explain_node)

    builder.add_edge(START, "weights")
    builder.add_edge("weights", "recommend")
    builder.add_edge("recommend", "explain")
    builder.add_edge("explain", END)

    return builder.compile()


# 그래프는 한 번만 만들어 두고 계속 쓴다.
graph = build_graph()
