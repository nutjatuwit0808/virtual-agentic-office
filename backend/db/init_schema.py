"""Create pgvector extension and RAG table on startup."""

from sqlalchemy import text

from db import models  # noqa: F401 - register RagEmbedding on Base.metadata
from db.base import Base
from db.session import engine


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
