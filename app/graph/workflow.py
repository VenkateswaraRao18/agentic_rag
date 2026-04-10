from langgraph.graph import END, START, StateGraph

from app.graph.nodes import classify_intent, generate_answer, maybe_call_tool, retrieve_docs
from app.graph.state import AgentState
from app.services.retriever import Retriever


def build_graph(retriever: Retriever):
    graph = StateGraph(AgentState)

    graph.add_node("classify", classify_intent)
    graph.add_node("retrieve", lambda s: retrieve_docs(s, retriever))
    graph.add_node("tool", maybe_call_tool)
    graph.add_node("answer", generate_answer)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "tool")
    graph.add_edge("tool", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
