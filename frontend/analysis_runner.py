"""Background analysis execution for the responsive Streamlit frontend."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import threading
import time
from typing import Any
from uuid import uuid4

from api_client import ApiClient, ApiError
from performance_planning_qa.cancellation import AnalysisCancelled, CancellationToken


@dataclass(frozen=True)
class AnalysisSnapshot:
    job_id: str
    session_id: str
    question: str
    progress: str
    reasoning: str
    elapsed_seconds: float
    done: bool
    stopping: bool


@dataclass
class AnalysisJob:
    """Thread-safe state for one analysis request."""

    job_id: str
    base_url: str
    session_id: str
    question: str
    dry_run: bool
    started_at: float = field(default_factory=time.monotonic)
    _progress: str = field(default="Connecting to the analysis service", init=False)
    _reasoning_parts: list[str] = field(default_factory=list, init=False, repr=False)
    _future: Future[dict[str, Any]] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _cancellation_token: CancellationToken = field(
        default_factory=CancellationToken,
        init=False,
        repr=False,
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def attach(self, future: Future[dict[str, Any]]) -> None:
        with self._lock:
            self._future = future

    def update_progress(self, message: str) -> None:
        cleaned = " ".join(str(message).split())
        if not cleaned:
            return
        with self._lock:
            if cleaned != self._progress:
                self._progress = cleaned[:240]

    def append_reasoning(self, content: str) -> None:
        if not content:
            return
        with self._lock:
            self._reasoning_parts.append(content)

    def cancel(self) -> None:
        self.update_progress("Stopping analysis")
        self._cancellation_token.cancel()

    @property
    def cancellation_token(self) -> CancellationToken:
        return self._cancellation_token

    def snapshot(self) -> AnalysisSnapshot:
        with self._lock:
            progress = self._progress
            reasoning = "".join(self._reasoning_parts)
            future = self._future
        return AnalysisSnapshot(
            job_id=self.job_id,
            session_id=self.session_id,
            question=self.question,
            progress=progress,
            reasoning=reasoning,
            elapsed_seconds=max(0.0, time.monotonic() - self.started_at),
            done=future.done() if future is not None else False,
            stopping=self._cancellation_token.cancelled,
        )

    def result(self) -> dict[str, Any]:
        with self._lock:
            future = self._future
        if future is None:
            raise RuntimeError("Analysis job has not started")
        return future.result()


class AnalysisRunner:
    """Own bounded workers for one Streamlit browser session."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            # A replacement must be able to start while a cancelled worker is
            # still unwinding its network/driver resources.
            max_workers=4,
            thread_name_prefix="ppqa-analysis",
        )
        self._active_job: AnalysisJob | None = None
        self._lock = threading.Lock()

    def start(
        self,
        *,
        base_url: str,
        session_id: str,
        question: str,
        dry_run: bool,
    ) -> AnalysisJob:
        with self._lock:
            if self._active_job is not None:
                raise RuntimeError("An analysis is already running in this session")
            job = AnalysisJob(
                job_id=str(uuid4()),
                base_url=base_url,
                session_id=session_id,
                question=question,
                dry_run=dry_run,
            )
            self._active_job = job
            try:
                future = self._executor.submit(_run_analysis, job)
            except Exception:
                self._active_job = None
                raise
            job.attach(future)
            return job

    def active_job(self) -> AnalysisJob | None:
        with self._lock:
            return self._active_job

    def clear(self, job_id: str) -> None:
        with self._lock:
            if self._active_job is not None and self._active_job.job_id == job_id:
                self._active_job = None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._active_job
            if job is None or job.job_id != job_id:
                return False
        job.cancel()
        with self._lock:
            if self._active_job is job:
                # Detach immediately. The worker may finish cleanup in the
                # background, but the composer can accept the next question.
                self._active_job = None
        return True

    def close(self) -> None:
        with self._lock:
            job = self._active_job
        if job is not None:
            job.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)


def _run_analysis(job: AnalysisJob) -> dict[str, Any]:
    client = ApiClient(job.base_url)

    def cancel_request() -> None:
        # CancellationToken callbacks run on Streamlit's UI thread. Keep that
        # path instant and perform network cleanup on a short-lived daemon.
        def interrupt_in_background() -> None:
            client.cancel_active_stream()
            client.cancel_analysis(job.job_id)

        threading.Thread(
            target=interrupt_in_background,
            name=f"ppqa-cancel-{job.job_id[:8]}",
            daemon=True,
        ).start()

    job.cancellation_token.register(cancel_request)
    response: dict[str, Any] | None = None
    try:
        for event in client.ask_session_stream(
            job.session_id,
            job.question,
            dry_run=job.dry_run,
            request_id=job.job_id,
            cancellation_token=job.cancellation_token,
        ):
            job.cancellation_token.raise_if_cancelled()
            event_type = event.get("event")
            if event_type == "progress":
                job.update_progress(str(event.get("message") or "Running analysis"))
            elif event_type == "reasoning":
                job.append_reasoning(str(event.get("content") or ""))
            elif event_type == "result":
                response = event
            elif event_type == "error":
                raise ApiError(str(event.get("message") or "Analysis failed"))
            elif event_type == "cancelled":
                raise AnalysisCancelled("Analysis stopped by the user")
        job.cancellation_token.raise_if_cancelled()
        if response is None:
            raise ApiError("The analysis ended without returning a result")
        return response
    except AnalysisCancelled:
        raise
    except Exception as exc:
        if job.cancellation_token.cancelled:
            raise AnalysisCancelled("Analysis stopped by the user") from exc
        raise
    finally:
        client.close()
