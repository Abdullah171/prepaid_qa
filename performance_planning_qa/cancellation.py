"""Cooperative cancellation shared by frontend, API, and pipeline work."""

from __future__ import annotations

import threading
from typing import Callable


class AnalysisCancelled(RuntimeError):
    """Raised when a user stops an in-progress analysis."""


class CancellationToken:
    """Thread-safe cancellation signal with best-effort interruption hooks."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            callbacks = tuple(self._callbacks)
            self._callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception:
                # Cancellation is best-effort; one driver hook must not prevent
                # the remaining hooks from running.
                pass

    def register(self, callback: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            if self._event.is_set():
                call_now = True
            else:
                self._callbacks.append(callback)
                call_now = False
        if call_now:
            try:
                callback()
            except Exception:
                pass

        def unregister() -> None:
            with self._lock:
                try:
                    self._callbacks.remove(callback)
                except ValueError:
                    pass

        return unregister

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise AnalysisCancelled("Analysis stopped by the user")
