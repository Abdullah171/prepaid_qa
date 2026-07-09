"""FastAPI entry point for the performance planning Q&A pipeline."""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from performance_planning_qa.config import load_environment, load_settings
from performance_planning_qa.pipeline import NL2SQLPipeline


logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    dry_run: bool = False


class QueryResultResponse(BaseModel):
    columns: list[str]
    row_count: int
    elapsed_ms: int
    rows: list[dict[str, Any]]


class AskResponse(BaseModel):
    question: str
    sql: str | None
    needs_clarification: bool
    clarifying_question: str | None
    direct_answer: str | None
    validation_tables: list[str]
    dry_run: bool
    answer: str | None
    error: str | None
    prompt_log_paths: list[str]
    query_result: QueryResultResponse | None


class HealthResponse(BaseModel):
    status: str


def _cors_origins() -> list[str]:
    load_environment()
    raw_origins = os.getenv("API_CORS_ORIGINS")
    if raw_origins is None:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.pipeline = NL2SQLPipeline(settings)
    app.state.pipeline_lock = asyncio.Lock()
    try:
        yield
    finally:
        app.state.pipeline.close()


app = FastAPI(
    title="Performance Planning Q&A API",
    description="Natural-language analytics over performance planning Teradata tables.",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/ask", response_model=AskResponse)
async def ask(request_body: AskRequest, request: Request) -> dict[str, Any]:
    question = request_body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    pipeline = _get_pipeline(request)
    pipeline_lock: asyncio.Lock = request.app.state.pipeline_lock

    try:
        async with pipeline_lock:
            result = await run_in_threadpool(pipeline.ask, question, dry_run=request_body.dry_run)
    except Exception as exc:
        logger.exception("Failed to answer question")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result.to_dict()


def _get_pipeline(request: Request) -> NL2SQLPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline is not initialized")
    return pipeline


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
