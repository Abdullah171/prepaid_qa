"""Direct HTTP client for OpenAI-compatible GLM and MiniMax endpoints."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import re
import time
from typing import Any, Callable

import json_repair

from performance_planning_qa.config import LLMSettings


logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

ChatMessage = dict[str, str]
ReasoningCallback = Callable[[str], None]


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

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        log_empty_response: bool = True,
        reasoning_callback: ReasoningCallback | None = None,
    ) -> str:
        request_payload = {
            "model": self.settings.model,
            "messages": _with_current_date_context(messages),
            "temperature": temperature,
            "stream": self.settings.stream,
        }
        diagnostics = {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "endpoint": _completion_url(self.settings.endpoint),
        }

        for attempt in range(self.settings.max_retries + 1):
            try:
                headers = {
                    "Authorization": f"Bearer {self.settings.api_key}",
                    "Content-Type": "application/json",
                }
                if self.settings.stream:
                    stream_diagnostics: dict[str, Any] = {}
                    with self.client.stream(
                        "POST",
                        diagnostics["endpoint"],
                        headers=headers,
                        json=request_payload,
                    ) as response:
                        if response.status_code >= 400:
                            response.read()
                        response.raise_for_status()
                        content = _stream_completion_content(
                            response,
                            reasoning_callback=reasoning_callback,
                            diagnostics=stream_diagnostics,
                        )
                    diagnostics["stream"] = stream_diagnostics
                else:
                    response = self.client.post(
                        diagnostics["endpoint"],
                        headers=headers,
                        json=request_payload,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    content = _completion_content(payload)
                break
            except Exception as exc:
                response = getattr(exc, "response", None)
                if response is not None:
                    diagnostics["status_code"] = response.status_code
                    diagnostics["response"] = _safe_error_response(response)

                if attempt < self.settings.max_retries and _is_retryable_error(exc):
                    delay = self.settings.retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "Transient LLM request failure; retrying in %.1f seconds "
                        "(attempt %d/%d); diagnostics=%s",
                        delay,
                        attempt + 1,
                        self.settings.max_retries,
                        diagnostics,
                    )
                    time.sleep(delay)
                    continue

                diagnostics["attempts"] = attempt + 1
                logger.exception(
                    "Direct LLM HTTP request failed; diagnostics=%s", diagnostics
                )
                raise

        if not content.strip():
            if log_empty_response:
                logger.error("LLM returned an empty response; diagnostics=%s", diagnostics)
            stream_summary = diagnostics.get("stream")
            if isinstance(stream_summary, dict):
                raise RuntimeError(
                    "LLM returned an empty response. "
                    f"Stream diagnostics: {_format_stream_diagnostics(stream_summary)}"
                )
            raise RuntimeError("LLM returned an empty response.")
        return content.strip()

    def complete_json(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        fallback_key: str | None = None,
        log_empty_response: bool = True,
        reasoning_callback: ReasoningCallback | None = None,
    ) -> dict[str, Any]:
        text = self.complete(
            messages,
            temperature=temperature,
            log_empty_response=log_empty_response,
            reasoning_callback=reasoning_callback,
        )
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


def _stream_completion_content(
    response: Any,
    *,
    reasoning_callback: ReasoningCallback | None,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    """Collect answer content while forwarding reasoning SSE chunks.

    The optional diagnostics object contains metadata only.  It deliberately
    excludes generated text so logs do not expose reasoning or answer content.
    """

    content_parts: list[str] = []
    event_count = 0
    ignored_line_count = 0
    reasoning_chars = 0
    finish_reason: Any = None
    usage: Any = None
    delta_keys: set[str] = set()
    choice_keys: set[str] = set()

    for line in response.iter_lines():
        if not line.startswith("data:"):
            if line.strip():
                ignored_line_count += 1
            continue
        data = line[5:].strip()
        if not data:
            continue
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM returned an invalid streaming event.") from exc

        event_count += 1
        if isinstance(payload, dict) and payload.get("usage") is not None:
            usage = payload["usage"]

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            continue
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            choice_keys.update(str(key) for key in first_choice)
            if first_choice.get("finish_reason") is not None:
                finish_reason = first_choice["finish_reason"]
        delta = first_choice.get("delta") if isinstance(first_choice, dict) else None
        if not isinstance(delta, dict):
            continue

        delta_keys.update(str(key) for key in delta)

        reasoning = delta.get("reasoning_content")
        if not isinstance(reasoning, str):
            reasoning = delta.get("reasoning")
        if isinstance(reasoning, str) and reasoning and reasoning_callback is not None:
            reasoning_chars += len(reasoning)
            try:
                reasoning_callback(reasoning)
            except Exception:
                logger.debug("Reasoning callback failed", exc_info=True)
        elif isinstance(reasoning, str):
            reasoning_chars += len(reasoning)

        content = delta.get("content")
        if isinstance(content, str):
            content_parts.append(content)

    content = "".join(content_parts)
    if diagnostics is not None:
        diagnostics.update(
            {
                "event_count": event_count,
                "ignored_line_count": ignored_line_count,
                "reasoning_chars": reasoning_chars,
                "content_chars": len(content),
                "finish_reason": finish_reason,
                "choice_keys": sorted(choice_keys),
                "delta_keys": sorted(delta_keys),
                "usage": usage,
            }
        )
    return content


def _format_stream_diagnostics(diagnostics: dict[str, Any]) -> str:
    """Format bounded, non-content stream metadata for an exception message."""

    fields = (
        "event_count",
        "ignored_line_count",
        "reasoning_chars",
        "content_chars",
        "finish_reason",
        "choice_keys",
        "delta_keys",
        "usage",
    )
    return ", ".join(
        f"{field}={diagnostics.get(field)!r}"
        for field in fields
    )


def _safe_error_response(response: Any) -> str:
    """Return a bounded response excerpt for diagnostics without request secrets."""

    return response.text[:1000]


def _is_retryable_error(exc: Exception) -> bool:
    """Return whether a failed request is safe to retry automatically."""

    response = getattr(exc, "response", None)
    if response is not None:
        return response.status_code in RETRYABLE_STATUS_CODES

    try:
        import httpx
    except ImportError:
        return False
    return isinstance(exc, httpx.TransportError)


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
