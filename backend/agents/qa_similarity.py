"""QA feedback similarity — detect stagnant loops before repeating instructions."""

from __future__ import annotations

import math
from typing import Any

from agents.state import OfficeState
from memory_service import embed_texts_for_similarity

# Flag / artifact keys (merged into OfficeState.artifacts)
ARTIFACT_QA_STAGNANT_LOOP = "qa_stagnant_loop"
ARTIFACT_QA_LAST_FEEDBACK = "qa_last_feedback"
ARTIFACT_QA_FEEDBACK = "qa_feedback"
ARTIFACT_QA_STAGNANT_NOTE = "qa_stagnant_note"
ARTIFACT_QA_SIMILARITY_SCORE = "qa_similarity_score"

STAGNANT_SIMILARITY_THRESHOLD = 0.90
MIN_QA_FEEDBACK_CHARS = 24


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _lexical_jaccard(a: str, b: str) -> float:
    """Word-level Jaccard when embeddings are unavailable (rough proxy, not semantic)."""
    wa = {w for w in a.lower().split() if len(w) > 1}
    wb = {w for w in b.lower().split() if len(w) > 1}
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def previous_qa_feedback_from_state(state: OfficeState) -> str:
    """Latest QA feedback from messages, then persisted artifact."""
    msgs = state.get("messages") or []
    for m in reversed(msgs):
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "").lower() == "qa":
            prev = str(m.get("content") or "").strip()
            if prev:
                return prev
    arts = state.get("artifacts") or {}
    return str(arts.get(ARTIFACT_QA_LAST_FEEDBACK) or "").strip()


async def semantic_similarity_pair(a: str, b: str) -> float:
    """Cosine similarity of embeddings when possible; else lexical Jaccard."""
    a, b = a.strip(), b.strip()
    if not a or not b:
        return 0.0
    vecs = await embed_texts_for_similarity([a, b])
    if len(vecs) == 2 and vecs[0] and vecs[1] and len(vecs[0]) == len(vecs[1]):
        return cosine_similarity(vecs[0], vecs[1])
    return _lexical_jaccard(a, b)


def stagnant_artifacts(sim: float, new: str) -> dict[str, Any]:
    note = (
        f"Stagnant Loop: new QA feedback is ~{sim:.0%} semantically similar to the previous "
        f"feedback — repeated instructions with no meaningful change."
    )
    return {
        ARTIFACT_QA_STAGNANT_LOOP: True,
        ARTIFACT_QA_STAGNANT_NOTE: note,
        ARTIFACT_QA_SIMILARITY_SCORE: round(sim, 4),
        ARTIFACT_QA_FEEDBACK: new,
    }
