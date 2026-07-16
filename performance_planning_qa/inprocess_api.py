"""Expose the FastAPI app to Streamlit without opening another network port."""

from __future__ import annotations

import atexit
from functools import partial
import logging
import queue
import threading
from typing import Any, Iterator

from performance_planning_qa.user_messages import ANALYSIS_UNAVAILABLE_MESSAGE


logger = logging.getLogger(__name__)

_client: Any | None = None
_client_lock = threading.Lock()


def get_inprocess_api_client() -> Any:
    """Start the FastAPI lifespan once and return a process-wide test client."""
    global _client

    with _client_lock:
        if _client is not None:
            return _client

        # Import lazily so ordinary local deployments keep using real HTTP and
        # do not initialize the backend in the Streamlit process.
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app, raise_server_exceptions=False)
        try:
            client.__enter__()
        except Exception:
            client.close()
            raise

        _client = client
        atexit.register(_close_inprocess_api_client)
        return _client


def stream_inprocess_session_ask(
    session_id: str,
    question: str,
    *,
    dry_run: bool = False,
) -> Iterator[dict[str, Any]]:
    """Bridge pipeline progress out of TestClient's buffered ASGI transport."""

    client = get_inprocess_api_client()
    event_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def report_progress(message: str) -> None:
        event_queue.put({"event": "progress", "message": message})

    def run_analysis() -> None:
        try:
            from fastapi import HTTPException
            from main import _ask_session_impl, app
            from starlette.requests import Request

            request = Request(
                {
                    "type": "http",
                    "app": app,
                    "method": "POST",
                    "path": f"/sessions/{session_id}/ask/stream",
                    "headers": [],
                    "query_string": b"",
                    "scheme": "http",
                    "server": ("inprocess", 80),
                    "client": ("streamlit", 0),
                    "root_path": "",
                    "http_version": "1.1",
                }
            )
            call = partial(
                _ask_session_impl,
                session_id,
                question,
                dry_run=dry_run,
                request=request,
                progress_callback=report_progress,
            )
            payload = client.portal.call(call)
        except HTTPException:
            event_queue.put(
                {"event": "error", "message": ANALYSIS_UNAVAILABLE_MESSAGE}
            )
        except Exception:
            logger.exception("In-process session analysis failed")
            event_queue.put(
                {"event": "error", "message": ANALYSIS_UNAVAILABLE_MESSAGE}
            )
        else:
            event_queue.put({"event": "result", **payload})
        finally:
            event_queue.put(None)

    threading.Thread(target=run_analysis, daemon=True).start()
    while True:
        event = event_queue.get()
        if event is None:
            return
        yield event


def _close_inprocess_api_client() -> None:
    global _client

    with _client_lock:
        if _client is None:
            return
        client = _client
        _client = None
        client.__exit__(None, None, None)
