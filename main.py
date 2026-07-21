"""FastAPI entry point for the performance planning Q&A pipeline."""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
import json
import logging
import os
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from performance_planning_qa.chat_store import (
    DEFAULT_SESSION_TITLE,
    MAX_SESSION_TITLE_LENGTH,
    ChatMessage,
    ChatStore,
    make_session_title,
)
from performance_planning_qa.cancellation import AnalysisCancelled, CancellationToken
from performance_planning_qa.config import load_environment, load_settings
from performance_planning_qa.pipeline import NL2SQLPipeline
from performance_planning_qa.prompts import ChatTurn
from performance_planning_qa.user_messages import ANALYSIS_UNAVAILABLE_MESSAGE


logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4_000)
    dry_run: bool = False
    request_id: str | None = Field(default=None, max_length=128)


class _SessionAnalysisGate:
    """Serialize a chat while allowing cancelled work to be superseded."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._generation = 0
        self._active_generation: int | None = None
        self._active_token: CancellationToken | None = None

    async def acquire(
        self,
        cancellation_token: CancellationToken | None,
        *,
        waiting_callback: Callable[[], None] | None = None,
    ) -> int:
        loop = asyncio.get_running_loop()
        waiting_since: float | None = None
        waiting_reported = False

        async with self._condition:
            while self._active_generation is not None and not (
                self._active_token is not None and self._active_token.cancelled
            ):
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                if waiting_since is None:
                    waiting_since = loop.time()
                elif (
                    not waiting_reported
                    and waiting_callback is not None
                    and loop.time() - waiting_since >= 0.25
                ):
                    waiting_callback()
                    waiting_reported = True
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass

            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            self._generation += 1
            self._active_generation = self._generation
            self._active_token = cancellation_token
            return self._generation

    async def release(self, generation: int) -> None:
        async with self._condition:
            # A cancelled generation may finish after its replacement. It must
            # never release the replacement's lease.
            if self._active_generation != generation:
                return
            self._active_generation = None
            self._active_token = None
            self._condition.notify_all()


class QueryResultResponse(BaseModel):
    columns: list[str]
    row_count: int
    elapsed_ms: int
    rows: list[dict[str, Any]]


class ChartResponse(BaseModel):
    version: Literal[1]
    type: Literal["line", "bar", "area", "scatter", "pie", "donut"]
    title: str
    x: str
    y: list[str]
    series: str | None = None
    x_kind: Literal["temporal", "quantitative", "nominal"]
    trigger: Literal["explicit", "trend"]
    requested_type: Literal["line", "bar", "area", "scatter", "pie", "donut"] | None = None
    fallback_reason: str | None = None
    truncated: bool = False
    data: list[dict[str, Any]]


class CSVExportResponse(BaseModel):
    version: Literal[2]
    status: Literal["offered", "ready"]
    filename: str
    mime_type: Literal["text/csv"]
    columns: list[str]
    rows: list[list[str]]
    row_count: int
    source: Literal["displayed_answer_table"]


class AskResponse(BaseModel):
    question: str
    sql: str | None
    needs_clarification: bool
    clarifying_question: str | None
    direct_answer: str | None
    validation_tables: list[str]
    dry_run: bool
    answer: str | None
    chart: ChartResponse | None = None
    csv_export: CSVExportResponse | None = None
    error: str | None
    prompt_log_paths: list[str]
    query_result: QueryResultResponse | None


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_SESSION_TITLE_LENGTH)


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_SESSION_TITLE_LENGTH)


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    dry_run: bool
    metadata: dict[str, Any]
    created_at: datetime


class SessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]


class SessionAskResponse(BaseModel):
    session: ChatSessionResponse
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    result: AskResponse


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
    app.state.session_analysis_gates: dict[str, _SessionAnalysisGate] = {}
    app.state.session_analysis_locks_guard = asyncio.Lock()
    app.state.active_analysis_tokens: dict[str, CancellationToken] = {}
    app.state.active_analysis_tokens_guard = asyncio.Lock()
    app.state.chat_store = ChatStore(settings.chat_storage, settings.teradata)
    app.state.chat_store_lock = asyncio.Lock()
    await run_in_threadpool(app.state.chat_store.ensure_schema)
    try:
        yield
    finally:
        app.state.pipeline.close()
        app.state.chat_store.close()


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

    pipeline = _get_pipeline(request).fork()

    try:
        result = await run_in_threadpool(
            pipeline.ask,
            question,
            dry_run=request_body.dry_run,
        )
    except Exception as exc:
        logger.exception("Failed to answer question")
        raise HTTPException(
            status_code=500,
            detail=ANALYSIS_UNAVAILABLE_MESSAGE,
        ) from exc
    finally:
        pipeline.close(close_database=False)

    return result.to_dict()


@app.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(request: Request) -> list[dict[str, Any]]:
    chat_store = _get_chat_store(request)
    sessions = await _run_chat_store(request, chat_store.list_sessions)
    return [session.to_payload() for session in sessions]


@app.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request_body: CreateSessionRequest,
    request: Request,
) -> dict[str, Any]:
    chat_store = _get_chat_store(request)
    session = await _run_chat_store(request, chat_store.create_session, request_body.title)
    return session.to_payload()


@app.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, request: Request) -> dict[str, Any]:
    session, messages = await _load_session_with_messages(request, session_id)
    return {
        "session": session.to_payload(),
        "messages": [message.to_payload() for message in messages],
    }


@app.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: str,
    request_body: UpdateSessionRequest,
    request: Request,
) -> dict[str, Any]:
    chat_store = _get_chat_store(request)
    session = await _run_chat_store(
        request,
        chat_store.update_session_title,
        session_id,
        request_body.title,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_payload()


@app.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, request: Request) -> Response:
    chat_store = _get_chat_store(request)
    deleted = await _run_chat_store(request, chat_store.delete_session, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/sessions/{session_id}/ask", response_model=SessionAskResponse)
async def ask_session(
    session_id: str,
    request_body: AskRequest,
    request: Request,
) -> dict[str, Any]:
    question = request_body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    return await _ask_session_impl(
        session_id,
        question,
        dry_run=request_body.dry_run,
        request=request,
    )


@app.post("/sessions/{session_id}/ask/stream")
async def ask_session_stream(
    session_id: str,
    request_body: AskRequest,
    request: Request,
) -> StreamingResponse:
    """Stream analysis phases, followed by the ordinary session response."""

    question = request_body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    async def events():
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        cancellation_token = CancellationToken()
        if request_body.request_id is not None:
            await _register_active_analysis(
                request,
                request_body.request_id,
                cancellation_token,
            )

        def report_progress(message: str) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, ("progress", message))

        def report_reasoning(content: str) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, ("reasoning", content))

        analysis_task = asyncio.create_task(
            _ask_session_impl(
                session_id,
                question,
                dry_run=request_body.dry_run,
                request=request,
                progress_callback=report_progress,
                reasoning_callback=report_reasoning,
                cancellation_token=cancellation_token,
            )
        )
        last_event_at = loop.time()

        try:
            while not analysis_task.done():
                try:
                    event_name, content = await asyncio.wait_for(
                        event_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    if loop.time() - last_event_at >= 15:
                        yield ": keep-alive\n\n"
                        last_event_at = loop.time()
                    continue
                field = "content" if event_name == "reasoning" else "message"
                yield _sse_event(event_name, {field: content})
                last_event_at = loop.time()

            while not event_queue.empty():
                event_name, content = event_queue.get_nowait()
                field = "content" if event_name == "reasoning" else "message"
                yield _sse_event(event_name, {field: content})

            try:
                payload = await analysis_task
            except AnalysisCancelled:
                yield _sse_event("cancelled", {"message": "Analysis stopped"})
            except HTTPException:
                yield _sse_event("error", {"message": ANALYSIS_UNAVAILABLE_MESSAGE})
            except Exception:
                logger.exception("Failed to stream session answer")
                yield _sse_event("error", {"message": ANALYSIS_UNAVAILABLE_MESSAGE})
            else:
                yield _sse_event("result", payload)
        finally:
            cancellation_token.cancel()
            if request_body.request_id is not None:
                await _unregister_active_analysis(
                    request,
                    request_body.request_id,
                    cancellation_token,
                )
            if not analysis_task.done():
                analysis_task.add_done_callback(_consume_background_task)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/analysis/{request_id}/cancel")
async def cancel_analysis(request_id: str, request: Request) -> dict[str, bool]:
    """Cancel one streaming analysis without affecting newer chat work."""

    guard: asyncio.Lock = request.app.state.active_analysis_tokens_guard
    async with guard:
        token = request.app.state.active_analysis_tokens.get(request_id)
    if token is None:
        return {"cancelled": False}
    await run_in_threadpool(token.cancel)
    return {"cancelled": True}


async def _ask_session_impl(
    session_id: str,
    question: str,
    *,
    dry_run: bool,
    request: Request,
    progress_callback: Callable[[str], None] | None = None,
    reasoning_callback: Callable[[str], None] | None = None,
    cancellation_token: CancellationToken | None = None,
) -> dict[str, Any]:
    """Run and persist one session question for regular and streaming routes."""

    pipeline = _get_pipeline(request).fork()
    chat_store = _get_chat_store(request)
    session_gate = await _get_session_analysis_gate(request, session_id)
    gate_generation: int | None = None

    def report_queue_wait() -> None:
        if progress_callback is None:
            return
        try:
            progress_callback("Waiting for the previous request in this chat")
        except Exception:
            logger.debug("Queue progress callback failed", exc_info=True)

    try:
        # Keep load -> analysis -> persistence ordered so simultaneous follow-ups
        # cannot both reuse the same stale session result. A cancelled request's
        # generation is replaced immediately instead of holding up its successor.
        gate_generation = await session_gate.acquire(
            cancellation_token,
            waiting_callback=report_queue_wait,
        )
        session, messages = await _load_session_with_messages(request, session_id)
        chat_history = _pipeline_history_from_messages(messages)
        previous_result = _latest_assistant_result(messages)
        result = await run_in_threadpool(
            pipeline.ask,
            question,
            dry_run=dry_run,
            chat_history=chat_history,
            previous_result=previous_result,
            progress_callback=progress_callback,
            reasoning_callback=reasoning_callback,
            cancellation_token=cancellation_token,
        )
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        result_payload = result.to_dict()
        assistant_content = _assistant_content_from_result(result_payload)
        user_message = await _run_chat_store(
            request,
            chat_store.add_message,
            session_id=session_id,
            role="user",
            content=question,
            dry_run=dry_run,
        )
        assistant_message = await _run_chat_store(
            request,
            chat_store.add_message,
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            dry_run=dry_run,
            metadata=result_payload,
        )
        if session.message_count == 0 and session.title == DEFAULT_SESSION_TITLE:
            updated_session = await _run_chat_store(
                request,
                chat_store.update_session_title,
                session_id,
                make_session_title(question),
            )
            if updated_session is not None:
                session = updated_session
        else:
            latest_session = await _run_chat_store(
                request,
                chat_store.get_session,
                session_id,
            )
            if latest_session is not None:
                session = latest_session
    except (HTTPException, AnalysisCancelled):
        raise
    except Exception as exc:
        logger.exception("Failed to answer session question")
        raise HTTPException(
            status_code=500,
            detail=ANALYSIS_UNAVAILABLE_MESSAGE,
        ) from exc
    finally:
        if gate_generation is not None:
            await session_gate.release(gate_generation)
        pipeline.close(close_database=False)

    return {
        "session": session.to_payload(),
        "user_message": user_message.to_payload(),
        "assistant_message": assistant_message.to_payload(),
        "result": result_payload,
    }


def _consume_background_task(task: asyncio.Task[Any]) -> None:
    """Retrieve errors from work finishing after its stream disconnected."""

    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    serializable_payload = jsonable_encoder(payload)
    return (
        f"event: {event}\n"
        f"data: {json.dumps(serializable_payload, ensure_ascii=False)}\n\n"
    )


def _get_pipeline(request: Request) -> NL2SQLPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline is not initialized")
    return pipeline


def _get_chat_store(request: Request) -> ChatStore:
    chat_store = getattr(request.app.state, "chat_store", None)
    if chat_store is None:
        raise HTTPException(status_code=503, detail="Chat store is not initialized")
    return chat_store


async def _get_session_analysis_gate(
    request: Request,
    session_id: str,
) -> _SessionAnalysisGate:
    """Return the cancellation-aware coordinator for one chat."""

    guard: asyncio.Lock = request.app.state.session_analysis_locks_guard
    async with guard:
        gates: dict[str, _SessionAnalysisGate] = (
            request.app.state.session_analysis_gates
        )
        gate = gates.get(session_id)
        if gate is None:
            gate = _SessionAnalysisGate()
            gates[session_id] = gate
        return gate


async def _register_active_analysis(
    request: Request,
    request_id: str,
    cancellation_token: CancellationToken,
) -> None:
    guard: asyncio.Lock = request.app.state.active_analysis_tokens_guard
    async with guard:
        request.app.state.active_analysis_tokens[request_id] = cancellation_token


async def _unregister_active_analysis(
    request: Request,
    request_id: str,
    cancellation_token: CancellationToken,
) -> None:
    guard: asyncio.Lock = request.app.state.active_analysis_tokens_guard
    async with guard:
        tokens: dict[str, CancellationToken] = (
            request.app.state.active_analysis_tokens
        )
        if tokens.get(request_id) is cancellation_token:
            tokens.pop(request_id, None)


async def _run_chat_store(request: Request, func, *args, **kwargs):
    chat_store_lock: asyncio.Lock = request.app.state.chat_store_lock
    async with chat_store_lock:
        try:
            return await run_in_threadpool(func, *args, **kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Chat store operation failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _load_session_with_messages(
    request: Request,
    session_id: str,
) -> tuple[Any, list[ChatMessage]]:
    chat_store = _get_chat_store(request)
    chat_store_lock: asyncio.Lock = request.app.state.chat_store_lock
    async with chat_store_lock:
        try:
            session = await run_in_threadpool(chat_store.get_session, session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Chat session not found")
            messages = await run_in_threadpool(chat_store.list_messages, session_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to load chat session")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return session, messages


def _pipeline_history_from_messages(messages: list[ChatMessage]) -> list[ChatTurn]:
    history = []
    for message in messages[-20:]:
        content = message.content
        if message.role == "assistant":
            sql = message.metadata.get("sql")
            if sql:
                content = f"{content}\nSQL used for that answer:\n{sql}"
            chart = message.metadata.get("chart")
            if isinstance(chart, dict):
                chart_type = str(chart.get("type") or "chart")
                x_field = str(chart.get("x") or "").strip()
                y_fields = chart.get("y") or []
                if isinstance(y_fields, list):
                    y_label = ", ".join(str(field) for field in y_fields[:4])
                else:
                    y_label = str(y_fields)
                if x_field and y_label:
                    content = (
                        f"{content}\nVisualization shown: {chart_type} using "
                        f"{x_field} and {y_label}."
                    )
        history.append(ChatTurn(role=message.role, content=content))
    return history


def _latest_assistant_result(messages: list[ChatMessage]) -> dict[str, Any] | None:
    """Return immediate assistant metadata for result reuse or clarification intent."""

    if not messages or messages[-1].role != "assistant":
        return None
    metadata = messages[-1].metadata
    if isinstance(metadata, dict) and metadata:
        return metadata
    return None


def _assistant_content_from_result(result_payload: dict[str, Any]) -> str:
    if result_payload.get("answer"):
        return str(result_payload["answer"])
    if result_payload.get("clarifying_question"):
        return str(result_payload["clarifying_question"])
    if result_payload.get("direct_answer"):
        return str(result_payload["direct_answer"])
    if result_payload.get("error"):
        return ANALYSIS_UNAVAILABLE_MESSAGE
    if result_payload.get("sql"):
        return "I generated SQL for this request."
    return "I could not produce an answer for this request."


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
