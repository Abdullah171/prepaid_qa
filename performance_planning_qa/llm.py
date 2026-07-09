"""OpenAI-compatible client wrapper for STC MiniMax."""

from __future__ import annotations

import json
import re
from typing import Any
import json_repair

from performance_planning_qa.config import LLMSettings


ChatMessage = dict[str, str]


class MiniMaxClient:
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
        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            temperature=temperature,
            max_tokens=self.settings.max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned an empty response.")
        return content.strip()

    def complete_json(self, messages: list[ChatMessage], *, temperature: float, fallback_key: str | None = None) -> dict[str, Any]:
        text = self.complete(messages, temperature=temperature)
        return extract_json_object(text, fallback_key=fallback_key)


def extract_json_object(text: str, fallback_key: str | None = None) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""

    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(_first_balanced_object(stripped))
        except ValueError:
            parsed = json_repair.loads(stripped)

    if not isinstance(parsed, dict):
        if fallback_key:
            return {fallback_key: text.strip()}
        raise ValueError(f"Expected a JSON object from the LLM. Got {type(parsed).__name__}. Raw response:\n{text}")
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
