import time
from typing import Any, Optional

_broadcaster: Optional[Any] = None


def configure_broadcaster(broadcaster: Any) -> None:
    global _broadcaster
    _broadcaster = broadcaster


async def emit_thought(agent: str, thought: str) -> None:
    payload = {
        "type": "thought",
        "agent": agent,
        "thought": thought,
        "ts": time.time(),
    }
    if _broadcaster is not None:
        await _broadcaster.broadcast(payload)


async def emit_terminal(agent: str, line: str, stream: str = "stdout") -> None:
    payload = {
        "type": "terminal",
        "agent": agent,
        "line": line,
        "stream": stream,
        "ts": time.time(),
    }
    if _broadcaster is not None:
        await _broadcaster.broadcast(payload)
