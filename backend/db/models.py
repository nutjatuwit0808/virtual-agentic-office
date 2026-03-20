from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from core.config import settings
from db.base import Base


class RagEmbedding(Base):
    """Row format mirrors Pinecone-style upserts: id, embedding vector, optional metadata JSON."""

    __tablename__ = "rag_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.vector_dimension))
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class OutputArtifact(Base):
    """Writer (and future agents) outputs persisted on disk with metadata for the gallery."""

    __tablename__ = "output_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    preview: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
