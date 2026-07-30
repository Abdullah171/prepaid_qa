"""Direct HTTP client for OpenAI-compatible GLM and MiniMax endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import re
import threading
import time
from typing import Any, Callable

import json_repair

from performance_planning_qa.cancellation import AnalysisCancelled, CancellationToken
from performance_planning_qa.config import LLMSettings


logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})
GLM_REASONING_CHAR_LIMIT = 60_000

ChatMessage = dict[str, str]
ReasoningCallback = Callable[[str], None]


@dataclass(frozen=True)
class _StreamCompletion:
    content: str
    captured_reasoning: str
    reasoning_limit_reached: bool


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
        self._active_response: Any | None = None
        self._response_lock = threading.Lock()

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
        cancellation_token: CancellationToken | None = None,
        reasoning_fallback_instruction: str | None = None,
    ) -> str:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        contextualized_messages = _with_current_date_context(messages)
        request_payload = {
            "model": self.settings.model,
            "messages": contextualized_messages,
            "temperature": temperature,
            "stream": self.settings.stream,
        }
        diagnostics = {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "endpoint": _completion_url(self.settings.endpoint),
        }
        captured_reasoning: str | None = None

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
                        with self._response_lock:
                            self._active_response = response
                        unregister_cancel = (
                            cancellation_token.register(response.close)
                            if cancellation_token is not None
                            else None
                        )
                        try:
                            if response.status_code >= 400:
                                response.read()
                            response.raise_for_status()
                            stream_completion = _stream_completion_content(
                                response,
                                reasoning_callback=reasoning_callback,
                                cancellation_token=cancellation_token,
                                diagnostics=stream_diagnostics,
                                reasoning_char_limit=(
                                    GLM_REASONING_CHAR_LIMIT
                                    if self.settings.provider == "glm"
                                    else None
                                ),
                            )
                            content = stream_completion.content
                            if stream_completion.reasoning_limit_reached:
                                captured_reasoning = (
                                    stream_completion.captured_reasoning
                                )
                        finally:
                            if unregister_cancel is not None:
                                unregister_cancel()
                            with self._response_lock:
                                if self._active_response is response:
                                    self._active_response = None
                    diagnostics["stream"] = stream_diagnostics
                else:
                    response = self.client.post(
                        diagnostics["endpoint"],
                        headers=headers,
                        json=request_payload,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    content = _completion_content(payload)
                break
            except AnalysisCancelled:
                raise
            except Exception as exc:
                if cancellation_token is not None and cancellation_token.cancelled:
                    raise AnalysisCancelled("Analysis stopped by the user") from exc
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

        if captured_reasoning is not None:
            print(
                "GLM reasoning reached the "
                f"{GLM_REASONING_CHAR_LIMIT:,}-character limit. "
                "Entering non-thinking mode to finalize the response...",
                flush=True,
            )
            content = self._complete_glm_without_thinking(
                contextualized_messages,
                captured_reasoning=captured_reasoning,
                temperature=temperature,
                cancellation_token=cancellation_token,
                finalization_instruction=reasoning_fallback_instruction,
            )

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

    def _complete_glm_without_thinking(
        self,
        contextualized_messages: list[ChatMessage],
        *,
        captured_reasoning: str,
        temperature: float,
        cancellation_token: CancellationToken | None,
        finalization_instruction: str | None,
    ) -> str:
        """Ask GLM to finalize once after a runaway reasoning stream."""

        continuation_messages = [
            message.copy() for message in contextualized_messages
        ]
        continuation_messages.append(
            {
                "role": "user",
                "content": _reasoning_continuation_prompt(
                    captured_reasoning,
                    finalization_instruction=finalization_instruction,
                ),
            }
        )
        request_payload = {
            "model": self.settings.model,
            "messages": continuation_messages,
            "temperature": temperature,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        diagnostics = {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "endpoint": _completion_url(self.settings.endpoint),
            "reasoning_fallback": True,
        }

        for attempt in range(self.settings.max_retries + 1):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            try:
                with self.client.stream(
                    "POST",
                    diagnostics["endpoint"],
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                ) as response:
                    with self._response_lock:
                        self._active_response = response
                    unregister_cancel = (
                        cancellation_token.register(response.close)
                        if cancellation_token is not None
                        else None
                    )
                    try:
                        if response.status_code >= 400:
                            response.read()
                        response.raise_for_status()
                        response.read()
                        payload = response.json()
                    finally:
                        if unregister_cancel is not None:
                            unregister_cancel()
                        with self._response_lock:
                            if self._active_response is response:
                                self._active_response = None
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                content = _completion_content(payload)
                if not content.strip():
                    raise RuntimeError(
                        "GLM returned an empty non-thinking fallback response."
                    )
                return content.strip()
            except AnalysisCancelled:
                raise
            except Exception as exc:
                if cancellation_token is not None and cancellation_token.cancelled:
                    raise AnalysisCancelled("Analysis stopped by the user") from exc
                response = getattr(exc, "response", None)
                if response is not None:
                    diagnostics["status_code"] = response.status_code
                    diagnostics["response"] = _safe_error_response(response)

                if attempt < self.settings.max_retries and _is_retryable_error(exc):
                    delay = self.settings.retry_backoff_seconds * (2**attempt)
                    logger.warning(
                        "Transient non-thinking GLM fallback failure; retrying in "
                        "%.1f seconds (attempt %d/%d); diagnostics=%s",
                        delay,
                        attempt + 1,
                        self.settings.max_retries,
                        diagnostics,
                    )
                    time.sleep(delay)
                    continue

                diagnostics["attempts"] = attempt + 1
                logger.exception(
                    "Non-thinking GLM fallback request failed; diagnostics=%s",
                    diagnostics,
                )
                raise

    def complete_json(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        fallback_key: str | None = None,
        log_empty_response: bool = True,
        reasoning_callback: ReasoningCallback | None = None,
        cancellation_token: CancellationToken | None = None,
        reasoning_fallback_instruction: str | None = None,
    ) -> dict[str, Any]:
        text = self.complete(
            messages,
            temperature=temperature,
            log_empty_response=log_empty_response,
            reasoning_callback=reasoning_callback,
            cancellation_token=cancellation_token,
            reasoning_fallback_instruction=reasoning_fallback_instruction,
        )
        return extract_json_object(text, fallback_key=fallback_key)

    def close(self) -> None:
        with self._response_lock:
            active_response = self._active_response
        if active_response is not None:
            active_response.close()
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
    cancellation_token: CancellationToken | None = None,
    diagnostics: dict[str, Any] | None = None,
    reasoning_char_limit: int | None = None,
) -> _StreamCompletion:
    """Collect answer content while forwarding reasoning SSE chunks.

    The optional diagnostics object contains metadata only.  It deliberately
    excludes generated text so logs do not expose reasoning or answer content.
    """

    content_parts: list[str] = []
    captured_reasoning_parts: list[str] | None = (
        [] if reasoning_char_limit is not None else None
    )
    event_count = 0
    ignored_line_count = 0
    reasoning_chars = 0
    reasoning_limit_reached = False
    finish_reason: Any = None
    usage: Any = None
    delta_keys: set[str] = set()
    choice_keys: set[str] = set()

    for line in response.iter_lines():
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
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
        if isinstance(reasoning, str) and reasoning:
            forwarded_reasoning = reasoning
            if reasoning_char_limit is not None:
                remaining = max(reasoning_char_limit - reasoning_chars, 0)
                forwarded_reasoning = reasoning[:remaining]
                if captured_reasoning_parts is not None and forwarded_reasoning:
                    captured_reasoning_parts.append(forwarded_reasoning)

            reasoning_chars += len(forwarded_reasoning)
            if forwarded_reasoning and reasoning_callback is not None:
                try:
                    reasoning_callback(forwarded_reasoning)
                except Exception:
                    logger.debug("Reasoning callback failed", exc_info=True)

            if (
                reasoning_char_limit is not None
                and reasoning_chars >= reasoning_char_limit
            ):
                reasoning_limit_reached = True
                break

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
                "reasoning_limit_reached": reasoning_limit_reached,
                "content_chars": len(content),
                "finish_reason": finish_reason,
                "choice_keys": sorted(choice_keys),
                "delta_keys": sorted(delta_keys),
                "usage": usage,
            }
        )
    return _StreamCompletion(
        content=content,
        captured_reasoning=(
            "".join(captured_reasoning_parts)
            if captured_reasoning_parts is not None
            else ""
        ),
        reasoning_limit_reached=reasoning_limit_reached,
    )


def _reasoning_continuation_prompt(
    captured_reasoning: str,
    *,
    finalization_instruction: str | None,
) -> str:
    """Build the one-shot non-thinking instruction without logging its content."""

    instruction = finalization_instruction or (
        "Complete the original task now. Follow the original output contract exactly "
        "and output nothing else."
    )
    return (
        "The previous thinking-enabled attempt reached its reasoning limit before "
        "returning the final response. Every original message above remains available "
        "and authoritative. Treat the captured reasoning as unfinished working notes, "
        "not as a final answer.\n\n"
        "<captured_reasoning>\n"
        f"{captured_reasoning}\n"
        "</captured_reasoning>\n\n"
        "FINALIZATION INSTRUCTIONS — HIGHEST PRIORITY:\n"
        f"{instruction}\n\n"
        "Do not continue the reasoning. Produce the required final JSON now."
    )


def _format_stream_diagnostics(diagnostics: dict[str, Any]) -> str:
    """Format bounded, non-content stream metadata for an exception message."""

    fields = (
        "event_count",
        "ignored_line_count",
        "reasoning_chars",
        "reasoning_limit_reached",
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
