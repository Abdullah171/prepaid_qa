"""OpenAI-compatible client wrapper for the STC LiteLLM gateway."""

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
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "Missing LLM dependencies. Install project dependencies with `uv sync`."
                ) from exc

            self._client = OpenAI(
                base_url=self.settings.base_url,
                api_key=self.settings.api_key,
                http_client=httpx.Client(
                    verify=self.settings.verify_ssl,
                    timeout=self.settings.timeout_seconds,
                ),
            )
        return self._client

    def complete(self, messages: list[ChatMessage], *, temperature: float) -> str:
        stream = self.client.chat.completions.create(
            model=self.settings.model,
            messages=_with_current_date_context(messages),
            temperature=temperature,
            max_tokens=self.settings.max_tokens,
            stream=True,
        )
        parts: list[str] = []
        diagnostics: dict[str, Any] = {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "chunk_count": 0,
            "choice_count": 0,
            "chunks_without_choices": 0,
            "content_fragments": 0,
            "content_characters": 0,
            "reasoning_characters": 0,
            "refusal_characters": 0,
            "tool_call_chunks": 0,
            "finish_reasons": [],
            "response_ids": [],
            "usage": None,
        }
        finish_reasons: set[str] = set()
        response_ids: set[str] = set()

        try:
            for chunk in stream:
                diagnostics["chunk_count"] += 1

                response_id = getattr(chunk, "id", None)
                if response_id:
                    response_ids.add(str(response_id))

                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    diagnostics["usage"] = _model_payload(usage)

                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    diagnostics["chunks_without_choices"] += 1
                    continue

                diagnostics["choice_count"] += len(choices)
                for choice in choices:
                    finish_reason = getattr(choice, "finish_reason", None)
                    if finish_reason:
                        finish_reasons.add(str(finish_reason))

                    delta = getattr(choice, "delta", None)
                    if delta is None:
                        continue

                    content = getattr(delta, "content", None)
                    if content:
                        parts.append(content)
                        diagnostics["content_fragments"] += 1
                        diagnostics["content_characters"] += len(content)

                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        diagnostics["reasoning_characters"] += len(reasoning)

                    refusal = getattr(delta, "refusal", None)
                    if refusal:
                        diagnostics["refusal_characters"] += len(refusal)

                    if getattr(delta, "tool_calls", None):
                        diagnostics["tool_call_chunks"] += 1
        except Exception:
            diagnostics["finish_reasons"] = sorted(finish_reasons)
            diagnostics["response_ids"] = sorted(response_ids)
            logger.exception("LLM stream failed; diagnostics=%s", diagnostics)
            raise

        content = "".join(parts)
        if not content.strip():
            diagnostics["finish_reasons"] = sorted(finish_reasons)
            diagnostics["response_ids"] = sorted(response_ids)
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


def _model_payload(value: Any) -> Any:
    """Convert SDK metadata to a log-friendly value without response content."""

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return str(value)


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
