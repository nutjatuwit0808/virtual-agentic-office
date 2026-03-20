from langgraph.graph import END, StateGraph

from agents.nodes import develop_node, research_node
from agents.state import OfficeState, initial_office_state


def build_research_develop_graph():
    graph = StateGraph(OfficeState)
    graph.add_node("research", research_node)
    graph.add_node("develop", develop_node)
    graph.set_entry_point("research")
    graph.add_edge("research", "develop")
    graph.add_edge("develop", END)
    return graph.compile()


compiled_graph = build_research_develop_graph()


async def run_research_develop(topic: str = "New initiative") -> OfficeState:
    state = initial_office_state(topic=topic)
    result = await compiled_graph.ainvoke(state)
    return result  # type: ignore[return-value]
