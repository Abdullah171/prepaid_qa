"""HTTP client for the Performance Planning Q&A FastAPI backend."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading
from typing import Any, Iterator
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from performance_planning_qa.cancellation import AnalysisCancelled, CancellationToken


INPROCESS_API_BASE_URL = "inprocess://ppqa"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.05
DEFAULT_HEALTH_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 15.0
DEFAULT_STREAM_READ_TIMEOUT_SECONDS = 45.0
DEFAULT_CANCEL_CONNECT_TIMEOUT_SECONDS = 1.0
DEFAULT_CANCEL_READ_TIMEOUT_SECONDS = 2.0


class ApiError(RuntimeError):
    pass


@dataclass
class ApiClient:
    base_url: str
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    stream_read_timeout_seconds: float = DEFAULT_STREAM_READ_TIMEOUT_SECONDS
    _session: requests.Session = field(
        default_factory=requests.Session,
        init=False,
        repr=False,
        compare=False,
    )
    _active_stream_response: Any | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _stream_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        self.base_url = _normalize_base_url(self.base_url)
        retry = Retry(
            total=1,
            connect=1,
            read=0,
            status=1,
            allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
            status_forcelist=(502, 503, 504),
            backoff_factor=0.25,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=4,
            pool_maxsize=8,
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def health(self) -> dict[str, Any]:
        return self._request(
            "GET",
            "/health",
            read_timeout_seconds=DEFAULT_HEALTH_TIMEOUT_SECONDS,
        )

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/sessions")

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if title:
            payload["title"] = title
        return self._request("POST", "/sessions", json=payload)

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}")

    def update_session(self, session_id: str, title: str) -> dict[str, Any]:
        return self._request("PATCH", f"/sessions/{session_id}", json={"title": title})

    def delete_session(self, session_id: str) -> None:
        self._request("DELETE", f"/sessions/{session_id}", expect_json=False)

    def ask_session(
        self,
        session_id: str,
        question: str,
        *,
        dry_run: bool = False,
        enable_thinking: bool = True,
    ) -> dict[str, Any]:
        payload = {"question": question, "dry_run": dry_run}
        if not enable_thinking:
            payload["enable_thinking"] = False
        return self._request(
            "POST",
            f"/sessions/{session_id}/ask",
            json=payload,
        )

    def ask_session_stream(
        self,
        session_id: str,
        question: str,
        *,
        dry_run: bool = False,
        enable_thinking: bool = True,
        request_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield live progress events and the final session response."""

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        path = f"/sessions/{session_id}/ask/stream"
        payload = {
            "question": question,
            "dry_run": dry_run,
            "request_id": request_id,
        }
        if not enable_thinking:
            payload["enable_thinking"] = False
        if self.base_url == INPROCESS_API_BASE_URL:
            try:
                from performance_planning_qa.inprocess_api import (
                    stream_inprocess_session_ask,
                )

                yield from stream_inprocess_session_ask(
                    session_id,
                    question,
                    dry_run=dry_run,
                    enable_thinking=enable_thinking,
                    cancellation_token=cancellation_token,
                )
            except ApiError:
                raise
            except Exception as exc:
                raise ApiError(
                    f"Could not stream from the in-process API: {exc}"
                ) from exc
            return

        url = f"{self.base_url}{path}"
        try:
            with self._session.post(
                url,
                json=payload,
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                },
                timeout=(
                    self.connect_timeout_seconds,
                    self.stream_read_timeout_seconds,
                ),
                stream=True,
            ) as response:
                with self._stream_lock:
                    self._active_stream_response = response
                try:
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    yield from _iter_sse(
                        response,
                        cancellation_token=cancellation_token,
                    )
                finally:
                    with self._stream_lock:
                        if self._active_stream_response is response:
                            self._active_stream_response = None
        except AnalysisCancelled:
            raise
        except ApiError:
            raise
        except requests.RequestException as exc:
            if cancellation_token is not None and cancellation_token.cancelled:
                raise AnalysisCancelled("Analysis stopped by the user") from exc
            raise ApiError(f"Could not reach API at {self.base_url}: {exc}") from exc

    def cancel_analysis(self, request_id: str) -> None:
        """Best-effort signal that releases the backend chat immediately."""

        if self.base_url == INPROCESS_API_BASE_URL:
            return
        try:
            requests.post(
                f"{self.base_url}/analysis/{request_id}/cancel",
                timeout=(
                    DEFAULT_CANCEL_CONNECT_TIMEOUT_SECONDS,
                    DEFAULT_CANCEL_READ_TIMEOUT_SECONDS,
                ),
            )
        except requests.RequestException:
            # Closing the stream below remains a second cancellation path.
            pass

    def cancel_active_stream(self) -> None:
        """Close the active response so a stopped stream unblocks immediately."""

        with self._stream_lock:
            response = self._active_stream_response
        if response is not None:
            response.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expect_json: bool = True,
        read_timeout_seconds: float | None = None,
    ):
        if self.base_url == INPROCESS_API_BASE_URL:
            try:
                from performance_planning_qa.inprocess_api import (
                    get_inprocess_api_client,
                )

                response = get_inprocess_api_client().request(method, path, json=json)
            except Exception as exc:
                raise ApiError(f"Could not start the in-process API: {exc}") from exc
        else:
            url = f"{self.base_url}{path}"
            try:
                response = self._session.request(
                    method,
                    url,
                    json=json,
                    timeout=(
                        self.connect_timeout_seconds,
                        read_timeout_seconds or self.read_timeout_seconds,
                    ),
                )
            except requests.RequestException as exc:
                raise ApiError(f"Could not reach API at {self.base_url}: {exc}") from exc

        if response.status_code >= 400:
            raise ApiError(_error_message(response))
        if not expect_json or response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                f"API at {self.base_url} returned an invalid JSON response"
            ) from exc

    def close(self) -> None:
        self._session.close()


def _error_message(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("detail"):
        detail = str(payload["detail"])[:1000]
        return f"API error {response.status_code}: {detail}"
    response_text = str(getattr(response, "text", ""))[:1000]
    return f"API error {response.status_code}: {response_text}"


def _iter_sse(
    response: Any,
    *,
    cancellation_token: CancellationToken | None = None,
) -> Iterator[dict[str, Any]]:
    if response.status_code >= 400:
        raise ApiError(_error_message(response))

    event_name = "message"
    data_lines: list[str] = []
    for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            if data_lines:
                yield _decode_sse_event(event_name, data_lines)
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if data_lines:
        yield _decode_sse_event(event_name, data_lines)


def _decode_sse_event(event_name: str, data_lines: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as exc:
        raise ApiError("API returned an invalid progress event") from exc
    if not isinstance(payload, dict):
        raise ApiError("API returned an invalid progress event")
    return {**payload, "event": event_name}


def _normalize_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    if base_url == INPROCESS_API_BASE_URL:
        return base_url
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ApiError("API URL must be an http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ApiError("API URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ApiError("API URL must not contain a query string or fragment")
    return base_url
