"""Office Manager escalation: loop diagnosis, user options, and resume gate."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.json_utils import parse_json_object
from agents.qa_similarity import ARTIFACT_QA_STAGNANT_LOOP, ARTIFACT_QA_STAGNANT_NOTE
from agents.state import LOOP_COUNTER_STEP, OfficeState
from agents.thoughts import emit_thought
from core.config import settings

ARTIFACT_ESCALATION_SUMMARY = "escalation_summary"
ARTIFACT_ESCALATION_OPTIONS = "escalation_options"
ARTIFACT_USER_ESCALATION_CHOICE = "user_escalation_choice"
ARTIFACT_USER_NEW_INSTRUCTIONS = "user_new_instructions"

_DEFAULT_OPTIONS: list[dict[str, str]] = [
    {
        "id": "force_approve",
        "label": "Force approve",
        "description": "Accept the current output and stop the loop without further revisions.",
    },
    {
        "id": "change_instructions",
        "label": "Change instructions",
        "description": "Provide new guidance so agents can align (e.g. update style or scope).",
    },
    {
        "id": "terminate",
        "label": "Terminate task",
        "description": "Stop the workflow and do not continue the office run.",
    },
]


def _fallback_manager_content(state: OfficeState, loop_n: int) -> tuple[str, list[dict[str, str]]]:
    artifacts = state.get("artifacts") or {}
    if artifacts.get(ARTIFACT_QA_STAGNANT_LOOP):
        note = str(artifacts.get(ARTIFACT_QA_STAGNANT_NOTE) or "QA Stagnant Loop.")
        summary = (
            f"{note} "
            f"(loop_counter={loop_n}). New QA feedback was semantically too close to the prior round — "
            "repeated instructions without meaningful change."
        )
        return summary, [dict(o) for o in _DEFAULT_OPTIONS]
    msgs = state.get("messages") or []
    tail = msgs[-5:] if len(msgs) > 5 else msgs
    excerpt = json.dumps(tail, default=str)[:1200]
    summary = (
        f"Loop guard triggered (loop_counter={loop_n}). "
        f"Likely causes: repeated revisions between roles (e.g. QA rejecting drafts because "
        f"the Writer is not following the style guide), or agents stuck re-trying without new constraints. "
        f"Recent message excerpt: {excerpt}"
    )
    return summary, [dict(o) for o in _DEFAULT_OPTIONS]


async def _llm_escalation_report(state: OfficeState, loop_n: int) -> tuple[str, list[dict[str, str]]]:
    topic = str(state.get("topic") or "")
    artifacts = state.get("artifacts") or {}
    agent_status = state.get("agent_status") or {}
    terminal = state.get("terminal_feed") or []
    messages = state.get("messages") or []

    payload = {
        "topic": topic,
        "loop_counter": loop_n,
        "agent_status": agent_status,
        "artifact_keys": list(artifacts.keys()),
        "qa_stagnant_loop": bool(artifacts.get(ARTIFACT_QA_STAGNANT_LOOP)),
        "qa_stagnant_note": artifacts.get(ARTIFACT_QA_STAGNANT_NOTE),
        "recent_terminal": terminal[-15:],
        "recent_messages": messages[-12:],
    }
    prompt = (
        "You are the Office Manager. The workflow hit a loop / step limit, or QA flagged a stagnant feedback loop. "
        "Return JSON only with keys:\n"
        '- "loop_diagnosis": string — one concise paragraph on WHY the office is looping '
        "(e.g. QA vs Writer style, developer sandbox retries). Be specific to the signals below.\n"
        '- "options": array of exactly 3 objects, each with "id", "label", "description". '
        "Use these ids in order: force_approve, change_instructions, terminate.\n\n"
        f"Context:\n{json.dumps(payload, default=str, indent=2)}"
    )
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.3,
    )
    out = await model.ainvoke([HumanMessage(content=prompt)])
    text = out.content if isinstance(out.content, str) else str(out.content)
    data = parse_json_object(text)
    diagnosis = str(data.get("loop_diagnosis") or "").strip() or "Loop detected; root cause unclear."
    raw_opts = data.get("options")
    options: list[dict[str, str]] = []
    if isinstance(raw_opts, list):
        for item in raw_opts[:3]:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id") or "").strip()
            if not oid:
                continue
            options.append(
                {
                    "id": oid,
                    "label": str(item.get("label") or oid),
                    "description": str(item.get("description") or ""),
                }
            )
    if len(options) < 3:
        options = [dict(o) for o in _DEFAULT_OPTIONS]
    return diagnosis, options


async def office_manager_escalation_node(state: OfficeState) -> dict[str, Any]:
    """Office Manager: explain the loop and present options; office pauses before `await_user_decision`."""
    loop_n = int(state.get("loop_counter") or 0)
    await emit_thought(
        "pm",
        "Office Manager: diagnosing loop and preparing options for the user.",
    )

    if settings.google_api_key:
        try:
            summary, options = await _llm_escalation_report(state, loop_n)
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            summary, options = _fallback_manager_content(state, loop_n)
            summary = f"{summary}\n\n(Manager LLM parse failed: {e!s})"
    else:
        summary, options = _fallback_manager_content(state, loop_n)

    options_text = json.dumps(options, indent=2)
    return {
        **LOOP_COUNTER_STEP,
        "messages": [
            {
                "role": "pm",
                "content": (
                    f"**Office Manager — escalation**\n\n{summary}\n\n"
                    f"**Your options:**\n{options_text}"
                ),
            }
        ],
        "current_phase": "escalation",
        "run_status": "AWAITING_USER",
        "artifacts": {
            ARTIFACT_ESCALATION_SUMMARY: summary,
            ARTIFACT_ESCALATION_OPTIONS: options,
        },
        "agent_status": {
            "pm": "thinking",
            "researcher": "idle",
            "developer": "idle",
            "writer": "idle",
            "qa": "idle",
        },
        "terminal_feed": [
            "[Office Manager] Workflow paused for your decision (see options in messages).",
        ],
    }


async def await_user_decision_node(state: OfficeState) -> dict[str, Any]:
    """Runs after the user resumes from interrupt; records the chosen path."""
    arts = state.get("artifacts") or {}
    choice = str(arts.get(ARTIFACT_USER_ESCALATION_CHOICE) or "").strip() or "terminate"
    extra = arts.get(ARTIFACT_USER_NEW_INSTRUCTIONS)
    extra_s = str(extra).strip() if extra is not None else ""

    if choice == "force_approve":
        rs = "RESOLVED_FORCE_APPROVE"
        line = "[Office Manager] User chose: Force approve."
    elif choice == "change_instructions":
        rs = "RESOLVED_CHANGE_INSTRUCTIONS"
        line = (
            f"[Office Manager] User chose: Change instructions."
            + (f" Notes: {extra_s[:2000]}" if extra_s else "")
        )
    else:
        rs = "RESOLVED_TERMINATE"
        line = "[Office Manager] User chose: Terminate task."

    await emit_thought("pm", line.replace("[Office Manager] ", ""))

    updates: dict[str, Any] = {
        "messages": [{"role": "pm", "content": line}],
        "current_phase": "resolved",
        "run_status": rs,
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "developer": "idle",
            "writer": "idle",
            "qa": "idle",
        },
        "terminal_feed": [line],
    }
    if extra_s and choice == "change_instructions":
        updates["artifacts"] = {ARTIFACT_USER_NEW_INSTRUCTIONS: extra_s}
    return updates
