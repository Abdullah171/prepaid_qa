"""Direct HTTP client for OpenAI-compatible GLM and MiniMax endpoints."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import re
from typing import Any

import json_repair

from performance_planning_qa.config import LLMSettings


logger = logging.getLogger(__name__)

ChatMessage = dict[str, str]


def _with_current_date_context(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Return a copy of the messages with fresh date context for the LLM."""

    now = datetime.now().astimezone()
    date_context = (
        f"Current date: {now.date().isoformat()} ({now.strftime('%A')}). "
        "Use this date to resolve relative time expressions such as today, yesterday, "
        "this month, this year, last N months, and previous N months. Do not assume the "
        "supplied data is current or complete "
        "through this date."
    )

    contextualized = [message.copy() for message in messages]
    for message in contextualized:
        if message.get("role") == "system":
            message["content"] = f"{date_context}\n\n{message.get('content', '')}"
            return contextualized

    return [{"role": "system", "content": date_context}, *contextualized]


class LiteLLMClient:
    def __init__(self, settings: LLMSettings):
        settings.validate()
        self.settings = settings
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:
                raise RuntimeError(
                    "Missing LLM dependencies. Install them with "
                    "`python -m pip install -r requirements.txt`."
                ) from exc

            self._client = httpx.Client(
                verify=self.settings.verify_ssl,
                timeout=self.settings.timeout_seconds,
            )
        return self._client

    def complete(self, messages: list[ChatMessage], *, temperature: float) -> str:
        request_payload = {
            "model": self.settings.model,
            "messages": _with_current_date_context(messages),
            "temperature": temperature,
            "max_tokens": self.settings.max_tokens,
            "stream": False,
        }
        diagnostics = {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "endpoint": _completion_url(self.settings.endpoint),
        }

        try:
            response = self.client.post(
                diagnostics["endpoint"],
                headers={
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            payload = response.json()
            content = _completion_content(payload)
        except Exception as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                diagnostics["status_code"] = response.status_code
                diagnostics["response"] = _safe_error_response(response)
            logger.exception("Direct LLM HTTP request failed; diagnostics=%s", diagnostics)
            raise

        if not content.strip():
            logger.error("LLM returned an empty response; diagnostics=%s", diagnostics)
            raise RuntimeError("LLM returned an empty response.")
        return content.strip()

    def complete_json(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        fallback_key: str | None = None,
    ) -> dict[str, Any]:
        text = self.complete(messages, temperature=temperature)
        return extract_json_object(text, fallback_key=fallback_key)

    def close(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None


def _completion_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return f"{endpoint}/chat/completions"


def _completion_content(payload: Any) -> str:
    """Extract assistant text from an OpenAI-compatible HTTP response."""

    if not isinstance(payload, dict):
        raise RuntimeError("LLM response must be a JSON object.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response did not contain any choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("LLM response contained an invalid choice.")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM response did not contain an assistant message.")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    raise RuntimeError("LLM assistant message did not contain text content.")


def _safe_error_response(response: Any) -> str:
    """Return a bounded response excerpt for diagnostics without request secrets."""

    return response.text[:1000]


def extract_json_object(text: str, fallback_key: str | None = None) -> dict[str, Any]:
    """Extract an object, repairing common LLM JSON mistakes when necessary."""

    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    candidates = [stripped]
    try:
        object_fragment = _first_balanced_object(stripped)
    except ValueError:
        object_fragment = None
    if object_fragment and object_fragment != stripped:
        candidates.append(object_fragment)

    parsed: Any = None
    parsed_found = False
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        parsed_found = True
        break

    repair_error: Exception | None = None
    if not parsed_found:
        # Prefer the isolated object over surrounding prose. Fall back to the
        # complete response for unterminated objects that cannot be isolated.
        for candidate in reversed(candidates):
            try:
                repaired = json_repair.loads(candidate)
            except Exception as exc:  # json-repair can raise several parser errors
                repair_error = exc
                continue
            parsed = repaired
            parsed_found = True
            if isinstance(repaired, dict):
                break

    if not parsed_found:
        if fallback_key:
            return {fallback_key: text.strip()}
        raise ValueError("Could not parse or repair the LLM response as JSON.") from repair_error

    if not isinstance(parsed, dict):
        if fallback_key:
            return {fallback_key: text.strip()}
        raise ValueError(
            f"Expected a JSON object from the LLM. Got {type(parsed).__name__}."
        )
    return parsed


def _first_balanced_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Unterminated JSON object in LLM response.")
