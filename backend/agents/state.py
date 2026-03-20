from operator import add
from typing import Annotated, TypedDict


def merge_dict(left: dict, right: dict) -> dict:
    if left is None:
        left = {}
    if right is None:
        right = {}
    return {**left, **right}


class OfficeState(TypedDict):
    """Shared LangGraph state for all office agents."""

    messages: Annotated[list[dict], add]
    current_phase: str
    artifacts: Annotated[dict, merge_dict]
    agent_status: Annotated[dict[str, str], merge_dict]
    topic: str


def initial_office_state(topic: str = "New initiative") -> OfficeState:
    return {
        "messages": [],
        "current_phase": "init",
        "artifacts": {},
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "dev": "idle",
            "qa": "idle",
        },
        "topic": topic,
    }
