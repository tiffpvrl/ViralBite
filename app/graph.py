from langgraph.graph import StateGraph, END
from app.graph_state import ViralBiteState
from app.agents import collector_node, analyst_node, insight_node


def build_graph():
    graph = StateGraph(ViralBiteState)

    graph.add_node("collector", collector_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("insight", insight_node)

    graph.set_entry_point("collector")
    graph.add_edge("collector", "analyst")
    graph.add_edge("analyst", "insight")
    graph.add_edge("insight", END)

    return graph.compile()