"""노드들을 이어 붙여 그래프를 만든다.

search_graph — weights_node 가 housing_override/weights_override 를 이미
내부에서 다 처리하므로, 갈림길 없이 직선으로만 잇는다 — add_conditional_edges 는 안 쓴다.
chat_graph — context 노드가 재료 글을 만들고 generate 노드가 답한다.
"""

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import ChatState, SearchState


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

    builder.add_node("context", nodes.chat_context_node)
    builder.add_node("generate", nodes.chat_generate_node)

    builder.add_edge(START, "context")
    builder.add_edge("context", "generate")
    builder.add_edge("generate", END)

    return builder.compile()


# 그래프는 한 번씩만 만들어 두고 계속 쓴다.
search_graph = build_search_graph()
chat_graph = build_chat_graph()
