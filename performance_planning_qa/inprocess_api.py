"""Expose the FastAPI app to Streamlit without opening another network port."""

from __future__ import annotations

import atexit
import threading
from typing import Any


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


def _close_inprocess_api_client() -> None:
    global _client

    with _client_lock:
        if _client is None:
            return
        client = _client
        _client = None
        client.__exit__(None, None, None)
