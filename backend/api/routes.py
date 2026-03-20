from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.streaming_manager import get_streaming_manager
from core.config import settings
from db.models import OutputArtifact
from db.session import get_session

router = APIRouter(prefix="/api", tags=["api"])


class GraphRunBody(BaseModel):
    topic: str = Field(default="New initiative", min_length=1, max_length=500)
    human_feedback: str | None = Field(
        default=None,
        max_length=8000,
        description="Optional user feedback to store in long-term memory for this run.",
    )


class GraphResumeBody(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    choice: Literal["force_approve", "change_instructions", "terminate"]
    new_instructions: str | None = Field(
        default=None,
        max_length=8000,
        description="Used when choice is change_instructions.",
    )


@router.post("/graph/run")
async def graph_run(body: GraphRunBody) -> dict:
    extra: dict = {}
    if body.human_feedback and body.human_feedback.strip():
        extra["human_feedback"] = body.human_feedback.strip()
    return await get_streaming_manager().run_research_writer(
        body.topic,
        extra_artifacts=extra or None,
    )


@router.post("/graph/resume")
async def graph_resume(body: GraphResumeBody) -> dict:
    try:
        return await get_streaming_manager().resume_escalation(
            body.thread_id,
            body.choice,
            new_instructions=body.new_instructions,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/outputs")
async def list_outputs(session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(
        select(OutputArtifact).order_by(OutputArtifact.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "topic": r.topic,
                "filename": r.filename,
                "mime_type": r.mime_type,
                "size_bytes": r.size_bytes,
                "preview": r.preview,
                "created_at": r.created_at.isoformat(),
                "file_url": f"/api/outputs/{r.id}/file",
            }
            for r in rows
        ]
    }


@router.get("/outputs/{artifact_id}/file")
async def get_output_file(
    artifact_id: str,
    download: bool = Query(False, description="Set to download as attachment"),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    result = await session.execute(
        select(OutputArtifact).where(OutputArtifact.id == artifact_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Output not found")
    path = settings.resolved_storage_root / row.relative_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")
    headers: dict[str, str] = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{row.filename}"'
    return FileResponse(
        str(path),
        media_type=row.mime_type,
        headers=headers,
    )
