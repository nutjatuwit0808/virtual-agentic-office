from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://agentic:agentic@localhost:5432/agentic_office"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    vector_dimension: int = 1536
    rag_enabled: bool = True
    e2b_api_key: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    embedding_model: str = "models/gemini-embedding-001"
    storage_root: str = Field(
        default="storage",
        description="Directory for persisted agent outputs (relative to backend/ if not absolute).",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_storage_root(self) -> Path:
        root = Path(self.storage_root)
        if root.is_absolute():
            return root.resolve()
        backend_dir = Path(__file__).resolve().parent.parent
        return (backend_dir / root).resolve()


settings = Settings()
