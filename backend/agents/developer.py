"""Developer agent — LLM + E2B tools via LangGraph prebuilt ReAct."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from agents.prompts import DEVELOPER_SYSTEM_PROMPT
from agents.state import LOOP_COUNTER_STEP, OfficeState
from agents.thoughts import emit_thought
from core.config import settings
from integrations.e2b_sandbox import build_developer_tools, create_async_sandbox, kill_sandbox


def _final_assistant_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if not isinstance(m, AIMessage):
            continue
        c = m.content
        if isinstance(c, str) and c.strip():
            return c.strip()
        if isinstance(c, list):
            parts: list[str] = []
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif isinstance(block, str):
                    parts.append(block)
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


async def developer_node(state: OfficeState) -> dict[str, Any]:
    topic = state.get("topic", "the task")
    research = state.get("artifacts", {}).get("research_notes", "")
    await emit_thought("developer", f"Starting developer session for «{topic}»…")

    idle_all = {
        "pm": "idle",
        "researcher": "idle",
        "developer": "idle",
        "writer": "idle",
        "qa": "idle",
    }

    if not settings.google_api_key:
        summary = "Developer agent skipped: GOOGLE_API_KEY is not set."
        await emit_thought("developer", summary)
        return {
            **LOOP_COUNTER_STEP,
            "messages": [{"role": "developer", "content": summary}],
            "current_phase": "develop",
            "artifacts": {
                "developer_summary": summary,
                "developer_sandbox_log": "",
                "developer_files": {},
            },
            "agent_status": idle_all,
            "terminal_feed": [summary],
        }

    sandbox = await create_async_sandbox()
    if sandbox is None:
        await emit_thought(
            "developer",
            "E2B sandbox unavailable — tools return errors until E2B_API_KEY is configured.",
        )

    collector: dict[str, Any] = {}
    tools = build_developer_tools(sandbox, collector)

    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,
    )

    react = create_react_agent(model, tools, prompt=DEVELOPER_SYSTEM_PROMPT)

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Research notes from the researcher:\n{research}\n\n"
        "Use the sandbox to explore or validate these notes with short Python snippets, "
        "then provide a concise summary for the Writer."
    )

    try:
        out = await react.ainvoke({"messages": [("user", user_msg)]})
    except Exception as e:
        summary = f"Developer agent error: {e!s}"
        await emit_thought("developer", summary)
        await kill_sandbox(sandbox)
        log_lines = collector.get("session_log", [])
        return {
            **LOOP_COUNTER_STEP,
            "messages": [{"role": "developer", "content": summary}],
            "current_phase": "develop",
            "artifacts": {
                "developer_summary": summary,
                "developer_sandbox_log": "\n".join(log_lines),
                "developer_files": collector.get("files", {}),
            },
            "agent_status": idle_all,
            "terminal_feed": log_lines[-500:] if log_lines else [summary],
        }

    msgs = out.get("messages", [])
    summary = _final_assistant_text(msgs) or "Developer agent finished (no assistant text)."
    session_log = "\n".join(collector.get("session_log", []))
    files: dict[str, str] = dict(collector.get("files", {}))

    preview = summary[:500] + ("…" if len(summary) > 500 else "")
    await emit_thought("developer", preview)

    await kill_sandbox(sandbox)

    log_for_state = collector.get("session_log", [])[-500:]

    return {
        **LOOP_COUNTER_STEP,
        "messages": [{"role": "developer", "content": summary[:2000]}],
        "current_phase": "develop",
        "artifacts": {
            "developer_summary": summary,
            "developer_sandbox_log": session_log,
            "developer_files": files,
        },
        "agent_status": {
            "pm": "idle",
            "researcher": "idle",
            "developer": "idle",
            "writer": "thinking",
            "qa": "idle",
        },
        "terminal_feed": log_for_state,
    }
