"""E2B code sandbox — optional; returns None when API key is missing."""

from typing import Any, Optional

from core.config import settings


async def create_sandbox() -> Optional[Any]:
    if not settings.e2b_api_key:
        return None
    try:
        from e2b_code_interpreter import Sandbox  # type: ignore[import-untyped]

        return await Sandbox.create(api_key=settings.e2b_api_key)
    except Exception:
        return None


async def run_snippet(code: str) -> tuple[Optional[str], Optional[str]]:
    sandbox = await create_sandbox()
    if sandbox is None:
        return None, "E2B not configured"
    try:
        execution = await sandbox.run_code(code)
        out = getattr(execution, "logs", None)
        text = str(out) if out is not None else ""
        return text, None
    finally:
        try:
            await sandbox.close()
        except Exception:
            pass
