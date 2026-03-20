"""Postgres + pgvector RAG store — no-ops when RAG is disabled."""

import json

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import settings
from db.models import RagEmbedding
from db.session import async_session_factory


async def upsert_vectors(vectors: list[dict]) -> bool:
    """Pinecone-compatible batch: each item has id, values (embedding), optional metadata dict."""
    if not settings.rag_enabled:
        return False
    if not vectors:
        return True
    rows: list[dict] = []
    for v in vectors:
        vid = v.get("id")
        vals = v.get("values")
        if vid is None or vals is None:
            return False
        if len(vals) != settings.vector_dimension:
            return False
        rows.append(
            {
                "id": str(vid),
                "embedding": list(vals),
                "meta": v.get("metadata"),
            }
        )
    async with async_session_factory() as session:
        stmt = pg_insert(RagEmbedding).values(rows)
        # stmt.excluded keys match DB column names ("metadata"), not Column() objects.
        stmt = stmt.on_conflict_do_update(
            index_elements=[RagEmbedding.id],
            set_={
                RagEmbedding.embedding: stmt.excluded.embedding,
                RagEmbedding.meta: stmt.excluded.metadata,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return True


async def query_vectors(vector: list[float], top_k: int = 5) -> list[dict]:
    """Return Pinecone-like matches: id, score (cosine similarity), metadata."""
    if not settings.rag_enabled:
        return []
    if len(vector) != settings.vector_dimension:
        return []
    vec_str = "[" + ",".join(str(x) for x in vector) + "]"
    sql = text(
        """
        SELECT id,
               (1 - (embedding <=> CAST(:qv AS vector)))::float AS score,
               metadata
        FROM rag_embeddings
        ORDER BY embedding <=> CAST(:qv AS vector)
        LIMIT :k
        """
    )
    async with async_session_factory() as session:
        result = await session.execute(sql, {"qv": vec_str, "k": top_k})
        out: list[dict] = []
        for row in result.mappings():
            out.append(
                {
                    "id": row["id"],
                    "score": float(row["score"]),
                    "metadata": row["metadata"],
                }
            )
        return out


async def query_vectors_filtered(
    vector: list[float],
    top_k: int = 5,
    metadata_contains: dict | None = None,
) -> list[dict]:
    """Like query_vectors but only rows whose metadata JSONB contains all keys in metadata_contains."""
    if not settings.rag_enabled:
        return []
    if len(vector) != settings.vector_dimension:
        return []
    vec_str = "[" + ",".join(str(x) for x in vector) + "]"
    if metadata_contains:
        sql = text(
            """
            SELECT id,
                   (1 - (embedding <=> CAST(:qv AS vector)))::float AS score,
                   metadata
            FROM rag_embeddings
            WHERE metadata @> CAST(:meta AS jsonb)
            ORDER BY embedding <=> CAST(:qv AS vector)
            LIMIT :k
            """
        )
        params = {
            "qv": vec_str,
            "k": top_k,
            "meta": json.dumps(metadata_contains),
        }
    else:
        sql = text(
            """
            SELECT id,
                   (1 - (embedding <=> CAST(:qv AS vector)))::float AS score,
                   metadata
            FROM rag_embeddings
            ORDER BY embedding <=> CAST(:qv AS vector)
            LIMIT :k
            """
        )
        params = {"qv": vec_str, "k": top_k}
    async with async_session_factory() as session:
        result = await session.execute(sql, params)
        out: list[dict] = []
        for row in result.mappings():
            out.append(
                {
                    "id": row["id"],
                    "score": float(row["score"]),
                    "metadata": row["metadata"],
                }
            )
        return out
