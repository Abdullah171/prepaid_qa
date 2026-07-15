"""Run the FastAPI application on loopback for a combined Streamlit deployment."""

from __future__ import annotations

import atexit
import socket
import threading
import time

import uvicorn


DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0


class EmbeddedApi:
    """A Uvicorn server owned by the current Python process."""

    def __init__(self, startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(128)
        self.port = int(self._socket.getsockname()[1])

        config = uvicorn.Config(
            "main:app",
            host="127.0.0.1",
            port=self.port,
            log_level="info",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._run,
            name="ppqa-fastapi",
            daemon=True,
        )
        self._thread.start()
        self._wait_until_started(startup_timeout)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _run(self) -> None:
        self._server.run(sockets=[self._socket])

    def _wait_until_started(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                return
            if not self._thread.is_alive():
                self._socket.close()
                raise RuntimeError("The embedded FastAPI server stopped during startup.")
            time.sleep(0.05)

        self.stop()
        raise TimeoutError(
            f"The embedded FastAPI server did not start within {timeout:g} seconds."
        )

    def stop(self) -> None:
        if not self._thread.is_alive():
            return
        self._server.should_exit = True
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            self._server.force_exit = True
            self._thread.join(timeout=2)


_instance: EmbeddedApi | None = None
_instance_lock = threading.Lock()


def get_embedded_api_url() -> str:
    """Start the process-wide API once and return its private loopback URL."""
    global _instance

    with _instance_lock:
        if _instance is None:
            _instance = EmbeddedApi()
            atexit.register(_instance.stop)
        return _instance.url
