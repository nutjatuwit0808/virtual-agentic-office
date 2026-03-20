from operator import add
from typing import Annotated, TypedDict


def merge_dict(left: dict, right: dict) -> dict:
    if left is None:
        left = {}
    if right is None:
        right = {}
    return {**left, **right}


# Each node returns +1; LangGraph merges with operator.add.
LOOP_COUNTER_STEP: dict[str, int] = {"loop_counter": 1}


class OfficeState(TypedDict):
    """Shared LangGraph state for all office agents."""

    messages: Annotated[list[dict], add]
    current_phase: str
    run_status: str
    loop_counter: Annotated[int, add]
    artifacts: Annotated[dict, merge_dict]
    agent_status: Annotated[dict[str, str], merge_dict]
    topic: str
    terminal_feed: Annotated[list[str], add]


def initial_office_state(
    topic: str = "New initiative",
    extra_artifacts: dict | None = None,
) -> OfficeState:
    artifacts: dict = {}
    if extra_artifacts:
        artifacts = {
            k: v
            for k, v in extra_artifacts.items()
            if v is not None and (not isinstance(v, str) or v.strip())
        }
    return {
        "messages": [],
        "current_phase": "init",
        "run_status": "",
        "loop_counter": 0,
        "artifacts": artifacts,
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "developer": "idle",
            "writer": "idle",
            "qa": "idle",
        },
        "topic": topic,
        "terminal_feed": [],
    }
