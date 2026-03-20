from agents.state import OfficeState
from agents.thoughts import emit_thought


async def research_node(state: OfficeState) -> dict:
    topic = state.get("topic", "the task")
    await emit_thought("pm", f"Scoping research priorities for: {topic}")
    await emit_thought(
        "researcher",
        f"Gathering sources and summarizing landscape for «{topic}».",
    )
    return {
        "messages": [
            {
                "role": "researcher",
                "content": f"Research summary for «{topic}»: key risks and opportunities identified.",
            }
        ],
        "current_phase": "research",
        "artifacts": {
            "research_notes": f"Condensed findings on «{topic}» (mock).",
        },
        "agent_status": {
            "pm": "thinking",
            "researcher": "working",
            "dev": "idle",
            "qa": "idle",
        },
    }


async def develop_node(state: OfficeState) -> dict:
    notes = state.get("artifacts", {}).get("research_notes", "")
    await emit_thought("dev", "Translating research notes into a minimal implementation plan.")
    await emit_thought("qa", "Preparing test checklist for the upcoming build.")
    return {
        "messages": [
            {
                "role": "dev",
                "content": f"Draft implementation based on: {notes[:120]}...",
            }
        ],
        "current_phase": "develop",
        "artifacts": {
            "code_draft": "# prototype\nprint('hello from agentic office')\n",
        },
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "dev": "working",
            "qa": "thinking",
        },
    }
