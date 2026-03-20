import time
from typing import Any, Optional

_broadcaster: Optional[Any] = None


def configure_broadcaster(broadcaster: Any) -> None:
    global _broadcaster
    _broadcaster = broadcaster


async def emit_thought(agent: str, thought: str) -> None:
    payload = {"agent": agent, "thought": thought, "ts": time.time()}
    if _broadcaster is not None:
        await _broadcaster.broadcast(payload)
