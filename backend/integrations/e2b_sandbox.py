"""E2B code sandbox — AsyncSandbox + LangChain tools for the Developer agent."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from langchain_core.tools import tool

from agents.thoughts import emit_terminal
from core.config import settings

_MAX_FILE_CHARS = 100_000
_NO_SANDBOX = "E2B not configured (set E2B_API_KEY)."


def _format_execution_logs(logs: Any) -> str:
    if logs is None:
        return ""
    stdout = getattr(logs, "stdout", None) or []
    stderr = getattr(logs, "stderr", None) or []
    parts: list[str] = []
    if stdout:
        parts.append("stdout:\n" + "\n".join(str(x) for x in stdout))
    if stderr:
        parts.append("stderr:\n" + "\n".join(str(x) for x in stderr))
    return "\n\n".join(parts).strip()


async def create_async_sandbox() -> Optional[Any]:
    if not settings.e2b_api_key:
        return None
    try:
        from e2b_code_interpreter import AsyncSandbox

        return await AsyncSandbox.create(api_key=settings.e2b_api_key)
    except Exception:
        return None


async def kill_sandbox(sandbox: Any) -> None:
    if sandbox is None:
        return
    try:
        maybe = sandbox.kill()
        if asyncio.iscoroutine(maybe):
            await maybe
    except Exception:
        pass


def build_developer_tools(sandbox: Any | None, collector: dict[str, Any]) -> list[Any]:
    """Build LangChain tools bound to one sandbox session. collector accumulates logs and file reads."""

    session_log: list[str] = collector.setdefault("session_log", [])
    files_out: dict[str, str] = collector.setdefault("files", {})

    def _append_log(text: str) -> None:
        session_log.append(text)

    @tool
    async def run_python_code(code: str) -> str:
        """Execute Python in the E2B sandbox (persistent interpreter state across calls). Returns captured stdout/stderr."""
        if sandbox is None:
            _append_log(f"[run_python_code] {_NO_SANDBOX}")
            return _NO_SANDBOX

        async def on_stdout(msg: Any) -> None:
            line = getattr(msg, "line", str(msg))
            _append_log(f"[stdout] {line}")
            await emit_terminal("developer", line, "stdout")

        async def on_stderr(msg: Any) -> None:
            line = getattr(msg, "line", str(msg))
            _append_log(f"[stderr] {line}")
            await emit_terminal("developer", line, "stderr")

        try:
            execution = await sandbox.run_code(
                code,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
            )
        except Exception as e:
            err = f"run_code failed: {e!s}"
            _append_log(err)
            await emit_terminal("developer", err, "stderr")
            return err

        err = getattr(execution, "error", None)
        if err is not None:
            text = getattr(err, "message", None) or str(err)
            _append_log(f"[error] {text}")
            return f"Execution error: {text}"

        log_text = _format_execution_logs(getattr(execution, "logs", None))
        if not log_text:
            return "(no output)"
        return log_text

    @tool
    async def pip_install(packages: str) -> str:
        """Install pip packages in the sandbox. Pass a single package name or comma-separated names (e.g. 'pandas' or 'numpy, scipy')."""
        if sandbox is None:
            _append_log(f"[pip_install] {_NO_SANDBOX}")
            return _NO_SANDBOX

        names = [p.strip() for p in packages.replace(" ", ",").split(",") if p.strip()]
        if not names:
            return "No packages specified."

        code = (
            "import subprocess, sys\n"
            f"pkgs = {names!r}\n"
            "r = subprocess.run([sys.executable, '-m', 'pip', 'install', *pkgs], "
            "capture_output=True, text=True)\n"
            "print(r.stdout or '')\n"
            "print(r.stderr or '', file=sys.stderr)\n"
        )

        async def on_stdout(msg: Any) -> None:
            line = getattr(msg, "line", str(msg))
            _append_log(f"[pip stdout] {line}")
            await emit_terminal("developer", line, "stdout")

        async def on_stderr(msg: Any) -> None:
            line = getattr(msg, "line", str(msg))
            _append_log(f"[pip stderr] {line}")
            await emit_terminal("developer", line, "stderr")

        try:
            execution = await sandbox.run_code(
                code,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
            )
        except Exception as e:
            err = f"pip_install failed: {e!s}"
            _append_log(err)
            return err

        err = getattr(execution, "error", None)
        if err is not None:
            text = getattr(err, "message", None) or str(err)
            return f"pip error: {text}"

        return _format_execution_logs(getattr(execution, "logs", None)) or "pip finished."

    @tool
    async def read_sandbox_file(path: str) -> str:
        """Read a text file from the sandbox filesystem (absolute path, e.g. /home/user/output.txt)."""
        if sandbox is None:
            return _NO_SANDBOX
        try:
            text = await sandbox.files.read(path, format="text")
        except Exception as e:
            return f"read failed: {e!s}"
        if len(text) > _MAX_FILE_CHARS:
            snippet = text[:_MAX_FILE_CHARS] + "\n…(truncated)"
            files_out[path] = snippet
            return snippet
        files_out[path] = text
        _append_log(f"[read_file] {path} ({len(text)} chars)")
        return text

    return [run_python_code, pip_install, read_sandbox_file]
