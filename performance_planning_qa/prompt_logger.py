"""Write exact LLM prompts to local text files for inspection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from performance_planning_qa.config import LLMSettings, PromptLogSettings
from performance_planning_qa.llm import ChatMessage


@dataclass(frozen=True)
class PromptLogRecord:
    path: Path
    phase: str


class PromptLogger:
    def __init__(self, settings: PromptLogSettings, llm_settings: LLMSettings):
        self.settings = settings
        self.llm_settings = llm_settings

    def log(
        self,
        *,
        phase: str,
        messages: list[ChatMessage],
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> PromptLogRecord | None:
        if not self.settings.enabled:
            return None

        self.settings.directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}_{_slug(phase)}.txt"
        path = self.settings.directory / filename

        lines = [
            "LLM Prompt Log",
            f"timestamp_utc: {now.isoformat()}",
            f"phase: {phase}",
            f"provider: {self.llm_settings.provider}",
            f"model: {self.llm_settings.model}",
            f"base_url: {self.llm_settings.base_url}",
            f"temperature: {temperature}",
            f"max_tokens: {self.llm_settings.max_tokens}",
        ]
        if extra:
            for key, value in extra.items():
                lines.append(f"{key}: {value}")

        lines.append("")
        lines.append("Messages sent to the LLM:")
        for index, message in enumerate(messages, start=1):
            role = message.get("role", "")
            content = message.get("content", "")
            lines.extend(
                [
                    "",
                    f"----- message {index}: role={role} -----",
                    content,
                    f"----- end message {index} -----",
                ]
            )

        path.write_text("\n".join(lines), encoding="utf-8")
        return PromptLogRecord(path=path, phase=phase)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("_") or "prompt"
