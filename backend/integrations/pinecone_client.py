"""Pinecone vector store — optional; no-ops when API key is missing."""

from typing import Any, Optional

from core.config import settings


def get_pinecone_index() -> Optional[Any]:
    if not settings.pinecone_api_key or not settings.pinecone_index:
        return None
    try:
        from pinecone import Pinecone  # type: ignore[import-untyped]

        pc = Pinecone(api_key=settings.pinecone_api_key)
        return pc.Index(settings.pinecone_index)
    except Exception:
        return None


async def upsert_vectors(vectors: list[dict]) -> bool:
    index = get_pinecone_index()
    if index is None:
        return False
    index.upsert(vectors=vectors)
    return True


async def query_vectors(vector: list[float], top_k: int = 5) -> list[dict]:
    index = get_pinecone_index()
    if index is None:
        return []
    res = index.query(vector=vector, top_k=top_k, include_metadata=True)
    return res.get("matches", []) if isinstance(res, dict) else []
