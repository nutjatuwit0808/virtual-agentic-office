"""Streams LangGraph `astream_events` (v2) to the WebSocket broadcaster."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from agents.escalation import (
    ARTIFACT_ESCALATION_OPTIONS,
    ARTIFACT_ESCALATION_SUMMARY,
    ARTIFACT_USER_ESCALATION_CHOICE,
    ARTIFACT_USER_NEW_INSTRUCTIONS,
)
from agents.graph import compiled_graph, graph_runtime_config
from agents.graph_errors import state_after_recursion_limit
from agents.state import OfficeState, initial_office_state
from memory_service import ingest_from_state

# Graph node id -> frontend AgentRole id
NODE_TO_AGENT: dict[str, str] = {
    "research": "researcher",
    "developer": "developer",
    "writer": "writer",
    "qa": "qa",
    "escalation": "pm",
    "await_user_decision": "pm",
}

OFFICE_STATE_KEYS = frozenset(
    {
        "messages",
        "current_phase",
        "run_status",
        "loop_counter",
        "artifacts",
        "agent_status",
        "topic",
        "terminal_feed",
    }
)

_GRAPH_NODE_IDS = frozenset(NODE_TO_AGENT.keys())


def _now() -> float:
    return time.time()


def _node_from_event(ev: dict[str, Any]) -> Optional[str]:
    meta = ev.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("langgraph_node"):
        return str(meta["langgraph_node"])
    name = ev.get("name")
    if isinstance(name, str) and name in NODE_TO_AGENT:
        return name
    return None


def _node_from_checkpoint_ns(ev: dict[str, Any]) -> Optional[str]:
    """Resolve graph node id for nested runs (e.g. ReAct under developer) from checkpoint namespace."""
    meta = ev.get("metadata") or {}
    if not isinstance(meta, dict):
        return None
    ns = meta.get("langgraph_checkpoint_ns")
    if not isinstance(ns, str) or not ns.strip():
        return None
    # Segments like "developer:task-id" or "developer:uuid|agent:sub"
    for segment in ns.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        head = segment.split(":", 1)[0].strip()
        if head in _GRAPH_NODE_IDS:
            return head
    return None


def _agent_for_llm_event(ev: dict[str, Any]) -> str:
    node = _node_from_event(ev) or _node_from_checkpoint_ns(ev)
    if not node:
        return ""
    return str(NODE_TO_AGENT.get(node, node))


def _coerce_optional_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _extract_llm_usage(msg: Any) -> Optional[dict[str, int]]:
    """Normalize token counts from AIMessage / dict (LangChain + Google GenAI)."""
    if msg is None:
        return None

    inp = out = total = None

    um = getattr(msg, "usage_metadata", None)
    if um is None and isinstance(msg, dict):
        um = msg.get("usage_metadata")
    if isinstance(um, dict):
        inp = _coerce_optional_int(um.get("input_tokens"))
        out = _coerce_optional_int(um.get("output_tokens"))
        total = _coerce_optional_int(um.get("total_tokens"))

    rm = getattr(msg, "response_metadata", None)
    if rm is None and isinstance(msg, dict):
        rm = msg.get("response_metadata")
    if isinstance(rm, dict):
        if inp is None:
            inp = _coerce_optional_int(rm.get("prompt_token_count")) or _coerce_optional_int(
                rm.get("input_tokens")
            )
        if out is None:
            out = _coerce_optional_int(rm.get("candidates_token_count")) or _coerce_optional_int(
                rm.get("completion_tokens")
            ) or _coerce_optional_int(rm.get("output_tokens"))
        if total is None:
            total = _coerce_optional_int(rm.get("total_token_count")) or _coerce_optional_int(
                rm.get("total_tokens")
            )
        nested = rm.get("usage_metadata")
        if isinstance(nested, dict):
            if inp is None:
                inp = _coerce_optional_int(nested.get("input_tokens")) or _coerce_optional_int(
                    nested.get("prompt_token_count")
                )
            if out is None:
                out = _coerce_optional_int(nested.get("output_tokens")) or _coerce_optional_int(
                    nested.get("candidates_token_count")
                )
            if total is None:
                total = _coerce_optional_int(nested.get("total_tokens")) or _coerce_optional_int(
                    nested.get("total_token_count")
                )

    if inp is None and out is None and total is None:
        return None
    if inp is None:
        inp = 0
    if out is None:
        out = 0
    if total is None:
        total = inp + out
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": total}


def _looks_like_full_state(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and OFFICE_STATE_KEYS.issubset(obj.keys())
    )


_manager: Optional["StreamingManager"] = None


def configure_streaming_manager(broadcaster: Any) -> None:
    global _manager
    _manager = StreamingManager(broadcaster)


def get_streaming_manager() -> "StreamingManager":
    if _manager is None:
        raise RuntimeError("StreamingManager not configured; call configure_streaming_manager first")
    return _manager


def _empty_usage_row() -> dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _add_usage_row(
    acc: dict[str, dict[str, int]], agent: str, row: dict[str, int]
) -> None:
    if not agent:
        return
    cur = acc.setdefault(agent, _empty_usage_row())
    cur["input_tokens"] = int(cur["input_tokens"]) + int(row["input_tokens"])
    cur["output_tokens"] = int(cur["output_tokens"]) + int(row["output_tokens"])
    cur["total_tokens"] = int(cur["total_tokens"]) + int(row["total_tokens"])


def _usage_snapshot(acc: dict[str, dict[str, int]]) -> tuple[dict[str, Any], dict[str, int]]:
    by_agent = {k: dict(v) for k, v in acc.items()}
    totals = _empty_usage_row()
    for row in acc.values():
        totals["input_tokens"] += int(row["input_tokens"])
        totals["output_tokens"] += int(row["output_tokens"])
        totals["total_tokens"] += int(row["total_tokens"])
    return by_agent, totals


class StreamingManager:
    def __init__(self, broadcaster: Any) -> None:
        self._broadcaster = broadcaster
        self._usage_by_agent: dict[str, dict[str, int]] = {}

    def _reset_usage_accumulator(self) -> None:
        self._usage_by_agent = {}

    async def _send(self, payload: dict[str, Any]) -> None:
        payload.setdefault("ts", _now())
        await self._broadcaster.broadcast(payload)

    async def _broadcast_escalation_wait(self, thread_id: str, state: OfficeState) -> None:
        arts = state.get("artifacts") or {}
        raw_opts = arts.get(ARTIFACT_ESCALATION_OPTIONS)
        options: Any = raw_opts if isinstance(raw_opts, list) else []
        await self._send(
            {
                "type": "escalation_wait",
                "thread_id": thread_id,
                "run_status": state.get("run_status", ""),
                "summary": arts.get(ARTIFACT_ESCALATION_SUMMARY),
                "options": options,
            }
        )

    async def handle_langgraph_event(self, raw: dict[str, Any]) -> None:
        event_kind = raw.get("event")
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        node = _node_from_event(raw)

        if event_kind == "on_chain_start" and node:
            await self._send(
                {
                    "type": "node_start",
                    "node": node,
                    "agent": NODE_TO_AGENT.get(node, node),
                }
            )
            return

        if event_kind == "on_chain_end" and node:
            msg: dict[str, Any] = {
                "type": "node_end",
                "node": node,
                "agent": NODE_TO_AGENT.get(node, node),
            }
            out = data.get("output")
            if isinstance(out, dict) and "agent_status" in out:
                msg["agent_status"] = out["agent_status"]
            if isinstance(out, dict) and "loop_counter" in out:
                msg["loop_counter"] = int(out["loop_counter"])
            await self._send(msg)
            return

        if event_kind == "on_tool_start":
            tool_name = raw.get("name") or data.get("name") or "tool"
            tool_input = data.get("input")
            await self._send(
                {
                    "type": "tool_start",
                    "tool": str(tool_name),
                    "agent": node or "",
                    "detail": _short_repr(tool_input),
                }
            )
            return

        if event_kind == "on_tool_end":
            tool_name = raw.get("name") or data.get("name") or "tool"
            await self._send(
                {
                    "type": "tool_end",
                    "tool": str(tool_name),
                    "agent": node or "",
                    "detail": _short_repr(data.get("output")),
                }
            )
            return

        if event_kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            text = _extract_token_text(chunk)
            if text:
                await self._send(
                    {
                        "type": "token",
                        "agent": NODE_TO_AGENT.get(node, node or ""),
                        "node": node or "",
                        "text": text,
                    }
                )
            return

        if event_kind == "on_chat_model_end":
            out_msg = data.get("output")
            usage = _extract_llm_usage(out_msg)
            if usage:
                agent = _agent_for_llm_event(raw)
                if agent:
                    _add_usage_row(self._usage_by_agent, agent, usage)
                    await self._send(
                        {
                            "type": "llm_usage",
                            "agent": agent,
                            "node": node or "",
                            "input_tokens": usage["input_tokens"],
                            "output_tokens": usage["output_tokens"],
                            "total_tokens": usage["total_tokens"],
                        }
                    )
            return

        if event_kind == "on_chain_end" and not node:
            out = data.get("output")
            if _looks_like_full_state(out):
                by_agent, totals = _usage_snapshot(self._usage_by_agent)
                await self._send(
                    {
                        "type": "graph_end",
                        "agent_status": out.get("agent_status", {}),
                        "current_phase": out.get("current_phase", ""),
                        "run_status": out.get("run_status", ""),
                        "loop_counter": int(out.get("loop_counter") or 0),
                        "usage_by_agent": by_agent,
                        "usage_totals": totals,
                    }
                )

    async def run_research_writer(
        self,
        topic: str = "New initiative",
        extra_artifacts: dict | None = None,
    ) -> dict[str, Any]:
        self._reset_usage_accumulator()
        state = initial_office_state(topic=topic, extra_artifacts=extra_artifacts)
        final: Optional[OfficeState] = None
        thread_id = str(uuid.uuid4())
        cfg = graph_runtime_config(thread_id)

        try:
            async for ev in compiled_graph.astream_events(
                state, config=cfg, version="v2"
            ):
                await self.handle_langgraph_event(ev)
                if ev.get("event") == "on_chain_end":
                    out = (ev.get("data") or {}).get("output")
                    if _looks_like_full_state(out):
                        final = out  # type: ignore[assignment]

            snap = await compiled_graph.aget_state(cfg)
            paused = bool(snap.next) and any(
                n == "await_user_decision" for n in (snap.next or ())
            )
            if paused and snap.values:
                out_state = snap.values  # type: ignore[assignment]
                await self._broadcast_escalation_wait(thread_id, out_state)
                return {
                    "state": out_state,
                    "thread_id": thread_id,
                    "interrupted": True,
                }

            if final is not None:
                await ingest_from_state(final)
                return {
                    "state": final,
                    "thread_id": thread_id,
                    "interrupted": False,
                }

            result = await compiled_graph.ainvoke(state, config=cfg)
            snap2 = await compiled_graph.aget_state(cfg)
            paused2 = bool(snap2.next) and any(
                n == "await_user_decision" for n in (snap2.next or ())
            )
            if paused2 and snap2.values:
                out_state = snap2.values  # type: ignore[assignment]
                await self._broadcast_escalation_wait(thread_id, out_state)
                return {
                    "state": out_state,
                    "thread_id": thread_id,
                    "interrupted": True,
                }

            await ingest_from_state(result)
            return {
                "state": result,
                "thread_id": thread_id,
                "interrupted": False,
            }

        except GraphRecursionError as exc:
            locked = state_after_recursion_limit(
                topic, extra_artifacts=extra_artifacts, exc=exc
            )
            await self._send(
                {
                    "type": "graph_loop_lock",
                    "run_status": "LOCKED_BY_LOOP",
                    "message": (
                        "Graph recursion limit reached; workflow locked "
                        "(possible infinite loop)."
                    ),
                    "current_phase": locked.get("current_phase", "error"),
                }
            )
            return {
                "state": locked,
                "thread_id": thread_id,
                "interrupted": False,
            }

    async def resume_escalation(
        self,
        thread_id: str,
        choice: str,
        new_instructions: str | None = None,
    ) -> dict[str, Any]:
        """Continue after Office Manager escalation (user chose an option)."""
        cfg = graph_runtime_config(thread_id)
        arts: dict[str, Any] = {ARTIFACT_USER_ESCALATION_CHOICE: choice}
        if new_instructions and new_instructions.strip():
            arts[ARTIFACT_USER_NEW_INSTRUCTIONS] = new_instructions.strip()
        cmd = Command(update={"artifacts": arts})

        async for ev in compiled_graph.astream_events(
            cmd, config=cfg, version="v2"
        ):
            await self.handle_langgraph_event(ev)

        snap = await compiled_graph.aget_state(cfg)
        if not snap.values:
            raise RuntimeError("Resume produced no checkpoint state")
        out_state = snap.values  # type: ignore[assignment]

        await ingest_from_state(out_state)
        return {
            "state": out_state,
            "thread_id": thread_id,
            "interrupted": False,
        }


def _short_repr(obj: Any, limit: int = 200) -> str:
    try:
        s = json.dumps(obj, default=str) if obj is not None else ""
    except TypeError:
        s = repr(obj)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _extract_token_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        # AIMessageChunk-style
        c = chunk.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: list[str] = []
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts)
    if hasattr(chunk, "content"):
        c = getattr(chunk, "content", "")
        if isinstance(c, str):
            return c
    return ""
