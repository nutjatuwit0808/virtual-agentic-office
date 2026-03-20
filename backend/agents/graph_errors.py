"""Runtime error handling for compiled LangGraph runs."""

from __future__ import annotations

from langgraph.errors import GraphRecursionError

from agents.state import OfficeState, initial_office_state


def state_after_recursion_limit(
    topic: str,
    *,
    extra_artifacts: dict | None,
    exc: GraphRecursionError,
) -> OfficeState:
    """Build final OfficeState when the graph hits LangGraph's recursion cap (loop guard)."""
    base = initial_office_state(topic=topic, extra_artifacts=extra_artifacts)
    msg = (
        "[system] Workflow locked: graph recursion limit reached "
        "(possible loop). Increase the cap only if this is expected."
    )
    if str(exc).strip():
        msg = f"{msg} Detail: {exc}"
    base["run_status"] = "LOCKED_BY_LOOP"
    base["current_phase"] = "error"
    base["terminal_feed"] = [msg]
    return base
