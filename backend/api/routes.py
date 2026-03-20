from pydantic import BaseModel, Field
from fastapi import APIRouter

from agents.graph import run_research_develop

router = APIRouter(prefix="/api", tags=["api"])


class GraphRunBody(BaseModel):
    topic: str = Field(default="New initiative", min_length=1, max_length=500)


@router.post("/graph/run")
async def graph_run(body: GraphRunBody) -> dict:
    state = await run_research_develop(body.topic)
    return {"state": state}
