"""Long-term office memory: embed Final Deliverables and Human Feedback into pgvector."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from agents.state import OfficeState
from core.config import settings
from integrations.vector_store import query_vectors_filtered, upsert_vectors

# Canonical artifact keys (keep in sync with nodes and API)
ARTIFACT_FINAL_DELIVERABLE = "final_deliverable"
ARTIFACT_HUMAN_FEEDBACK = "human_feedback"
ARTIFACT_INTERNAL_KNOWLEDGE_CONTEXT = "internal_knowledge_context"

METADATA_SOURCE_KEY = "source"
METADATA_SOURCE_OFFICE_MEMORY = "office_memory"
METADATA_MEMORY_KIND = "memory_kind"

MemoryKind = Literal["final_deliverable", "human_feedback"]

_CHUNK_SIZE = 1800
_CHUNK_OVERLAP = 200

_embedder: GoogleGenerativeAIEmbeddings | None = None


def _get_embedder() -> GoogleGenerativeAIEmbeddings | None:
    global _embedder
    if not settings.google_api_key:
        return None
    if _embedder is None:
        try:
            _embedder = GoogleGenerativeAIEmbeddings(
                model=settings.embedding_model,
                google_api_key=settings.google_api_key,
                output_dimensionality=settings.vector_dimension,
            )
        except TypeError:
            _embedder = GoogleGenerativeAIEmbeddings(
                model=settings.embedding_model,
                google_api_key=settings.google_api_key,
            )
    return _embedder


def _chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= _CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - _CHUNK_OVERLAP)
    return chunks


def _chunk_id(topic: str, kind: MemoryKind, chunk_index: int, body: str) -> str:
    h = hashlib.sha256(f"{topic}|{kind}|{chunk_index}|{body}".encode()).hexdigest()
    return f"m_{h[:32]}"


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for each text; empty list if disabled or no API key."""
    if not settings.rag_enabled or not texts:
        return []
    emb = _get_embedder()
    if emb is None:
        return []
    return await asyncio.to_thread(emb.embed_documents, texts)


async def embed_texts_for_similarity(texts: list[str]) -> list[list[float]]:
    """Embeddings for semantic similarity (e.g. QA loop detection). Uses GOOGLE_API_KEY when set, independent of RAG."""
    if not texts:
        return []
    emb = _get_embedder()
    if emb is None:
        return []
    return await asyncio.to_thread(emb.embed_documents, texts)


async def embed_query(text: str) -> list[float]:
    if not settings.rag_enabled or not text.strip():
        return []
    emb = _get_embedder()
    if emb is None:
        return []
    return await asyncio.to_thread(emb.embed_query, text)


def _memory_filter() -> dict[str, Any]:
    return {METADATA_SOURCE_KEY: METADATA_SOURCE_OFFICE_MEMORY}


async def search_internal_knowledge(
    query: str,
    topic: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over stored office memory (deliverables + feedback)."""
    if not settings.rag_enabled:
        return []
    vec = await embed_query(f"{topic}\n\n{query}".strip())
    if len(vec) != settings.vector_dimension:
        return []
    rows = await query_vectors_filtered(
        vec,
        top_k=top_k,
        metadata_contains=_memory_filter(),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        text = ""
        if isinstance(meta, dict):
            text = str(meta.get("text", ""))
        out.append(
            {
                "id": row["id"],
                "score": row["score"],
                "memory_kind": meta.get(METADATA_MEMORY_KIND) if isinstance(meta, dict) else None,
                "topic": meta.get("topic") if isinstance(meta, dict) else None,
                "text": text,
            }
        )
    return out


def format_internal_knowledge_context(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return ""
    lines = ["### Prior office memory (retrieved)", ""]
    for i, m in enumerate(matches, 1):
        score = m.get("score", 0)
        mk = m.get("memory_kind") or "unknown"
        tx = (m.get("text") or "").strip()
        if not tx:
            continue
        preview = tx if len(tx) <= 1200 else tx[:1200] + "…"
        lines.append(f"{i}. **{mk}** (relevance {score:.3f})\n\n{preview}\n")
    return "\n".join(lines).strip()


async def ingest_from_state(state: OfficeState) -> None:
    """Upsert final deliverable and human feedback chunks from graph state."""
    if not settings.rag_enabled:
        return
    if state.get("run_status") in (
        "LOCKED_BY_LOOP",
        "AWAITING_USER",
        "RESOLVED_TERMINATE",
        "RESOLVED_CHANGE_INSTRUCTIONS",
    ):
        return
    topic = str(state.get("topic") or "").strip() or "untitled"
    artifacts = state.get("artifacts") or {}
    now = datetime.now(timezone.utc).isoformat()

    batches: list[dict] = []

    async def add_chunks(text: str, kind: MemoryKind) -> None:
        chunks = _chunk_text(text)
        if not chunks:
            return
        vectors_list = await embed_texts(chunks)
        if len(vectors_list) != len(chunks):
            return
        total = len(chunks)
        for i, (chunk, vec) in enumerate(zip(chunks, vectors_list)):
            if len(vec) != settings.vector_dimension:
                continue
            cid = _chunk_id(topic, kind, i, chunk)
            meta = {
                METADATA_SOURCE_KEY: METADATA_SOURCE_OFFICE_MEMORY,
                METADATA_MEMORY_KIND: kind,
                "topic": topic,
                "chunk_index": i,
                "chunk_total": total,
                "stored_at": now,
                "text": chunk,
            }
            batches.append(
                {
                    "id": cid,
                    "values": vec,
                    "metadata": meta,
                }
            )

    fd = artifacts.get(ARTIFACT_FINAL_DELIVERABLE)
    if isinstance(fd, str) and fd.strip():
        await add_chunks(fd, "final_deliverable")

    hf = artifacts.get(ARTIFACT_HUMAN_FEEDBACK)
    if isinstance(hf, str) and hf.strip():
        await add_chunks(hf, "human_feedback")

    if batches:
        await upsert_vectors(batches)
