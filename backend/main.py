from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.thoughts import configure_broadcaster
from api.routes import router as api_router
from api.websocket import router as ws_router, thought_broadcaster
from core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_broadcaster(thought_broadcaster)
    yield


app = FastAPI(title="AI Agentic Office API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
