"""Optional live facts to merge into research (httpx; failures are silent)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

# Topics that benefit from a spot commodity quote (USD/Oz is industry-standard).
_GOLD_TOPIC = re.compile(
    r"gold|ทอง|xau|spot\s*gold|ราคาทอง|gold\s*price",
    re.IGNORECASE,
)


async def fetch_supplemental_market_facts(topic: str) -> str:
    """Return a short markdown block with live-ish spot data, or empty string."""
    if not _GOLD_TOPIC.search(topic):
        return ""

    lines: list[str] = []
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    lines.append(
        f"- **As-of (UTC):** {now.strftime('%Y-%m-%d %H:%M')} — "
        f"“last week” in the user request is interpreted as ~{week_ago.date()}–{now.date()}."
    )

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get("https://api.metals.live/v1/spot/gold")
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return "\n".join(lines) + "\n- **Spot gold (USD/oz):** unavailable (network or API)."

    # API returns a bare number or a small JSON structure depending on version.
    spot: float | None = None
    if isinstance(data, (int, float)):
        spot = float(data)
    elif isinstance(data, list) and data:
        spot = float(data[0]) if isinstance(data[0], (int, float)) else None
    elif isinstance(data, dict):
        for k in ("price", "gold", "spot", "value"):
            v = data.get(k)
            if isinstance(v, (int, float)):
                spot = float(v)
                break

    if spot is not None:
        lines.append(
            f"- **Spot gold (USD/troy oz, live quote via metals.live):** ~{spot:,.2f}. "
            "Use this as a current anchor; daily “last week” series still needs a historical feed or manual verification."
        )
    else:
        lines.append(f"- **Spot gold:** raw API response could not be parsed: `{data!r}`")

    return "\n".join(lines)
