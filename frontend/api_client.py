"""HTTP client for the Performance Planning Q&A FastAPI backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


INPROCESS_API_BASE_URL = "inprocess://ppqa"


class ApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiClient:
    base_url: str
    timeout_seconds: float = 1220.0

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

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

    def ask_session(self, session_id: str, question: str, *, dry_run: bool = False) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/sessions/{session_id}/ask",
            json={"question": question, "dry_run": dry_run},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        expect_json: bool = True,
    ):
        if self.base_url.rstrip("/") == INPROCESS_API_BASE_URL:
            try:
                from performance_planning_qa.inprocess_api import (
                    get_inprocess_api_client,
                )

                response = get_inprocess_api_client().request(method, path, json=json)
            except Exception as exc:
                raise ApiError(f"Could not start the in-process API: {exc}") from exc
        else:
            url = f"{self.base_url.rstrip('/')}{path}"
            try:
                response = requests.request(
                    method,
                    url,
                    json=json,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise ApiError(f"Could not reach API at {self.base_url}: {exc}") from exc

        if response.status_code >= 400:
            raise ApiError(_error_message(response))
        if not expect_json or response.status_code == 204:
            return None
        return response.json()


def _error_message(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("detail"):
        return f"API error {response.status_code}: {payload['detail']}"
    return f"API error {response.status_code}: {response.text}"
