from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.developer import developer_node
from agents.escalation import await_user_decision_node, office_manager_escalation_node
from agents.nodes import qa_node, research_node, writer_node
from agents.qa_similarity import ARTIFACT_QA_STAGNANT_LOOP
from agents.state import OfficeState

# Step cap for the compiled graph (20–30). Applied at invoke/stream time via
# `graph_runtime_config()` — LangGraph does not accept this on `compile()`.
GRAPH_RECURSION_LIMIT = 25

# In-memory checkpoints (thread_id in RunnableConfig). Required for interrupts.
graph_checkpointer = MemorySaver()


def graph_runtime_config(thread_id: str) -> dict[str, Any]:
    return {
        "recursion_limit": GRAPH_RECURSION_LIMIT,
        "configurable": {"thread_id": thread_id},
    }


def should_continue(state: OfficeState) -> Literal["continue", "escalate"]:
    """Route to EscalationNode when too many agent nodes have executed."""
    if int(state.get("loop_counter") or 0) > 10:
        return "escalate"
    return "continue"


def route_after_qa(state: OfficeState) -> Literal["continue", "escalate"]:
    """Escalate when QA detects semantically duplicate feedback (stagnant loop)."""
    if state.get("artifacts", {}).get(ARTIFACT_QA_STAGNANT_LOOP):
        return "escalate"
    return "continue"


def build_research_writer_graph():
    graph = StateGraph(OfficeState)
    graph.add_node("research", research_node)
    graph.add_node("developer", developer_node)
    graph.add_node("writer", writer_node)
    graph.add_node("qa", qa_node)
    graph.add_node("escalation", office_manager_escalation_node)
    graph.add_node("await_user_decision", await_user_decision_node)
    graph.set_entry_point("research")
    graph.add_conditional_edges(
        "research",
        should_continue,
        {"continue": "developer", "escalate": "escalation"},
    )
    graph.add_conditional_edges(
        "developer",
        should_continue,
        {"continue": "writer", "escalate": "escalation"},
    )
    graph.add_conditional_edges(
        "writer",
        should_continue,
        {"continue": "qa", "escalate": "escalation"},
    )
    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {"continue": END, "escalate": "escalation"},
    )
    graph.add_edge("escalation", "await_user_decision")
    graph.add_edge("await_user_decision", END)
    # `escalation` runs first (Office Manager summary + options). Then we pause before
    # `await_user_decision` so the user can POST /api/graph/resume with a choice.
    return graph.compile(
        checkpointer=graph_checkpointer,
        interrupt_before=["await_user_decision"],
    )


compiled_graph = build_research_writer_graph()
