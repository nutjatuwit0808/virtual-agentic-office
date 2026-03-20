"""Shared JSON extraction for LLM outputs (markdown fences, etc.)."""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        if len(parts) >= 2:
            inner = parts[1]
            if inner.lstrip().startswith("json"):
                inner = inner.lstrip()[4:].lstrip()
            raw = inner
    return json.loads(raw)


def try_parse_json_dict(text: str) -> dict[str, Any] | None:
    """Like `parse_json_object`, but returns None on failure or non-object JSON."""
    try:
        obj = parse_json_object(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None
