"""Prompt construction for SQL generation and analytical answering."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from performance_planning_qa.context_loader import PromptContext


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


SQL_DOMAIN_GUIDANCE = ""
BUSINESS_TERM_GUIDANCE = ""
ANALYST_JOIN_FEW_SHOT_EXAMPLES = ""
ANALYST_QUESTION_FEW_SHOT_EXAMPLES = ""
SQL_SYSTEM_PROMPT = ""
ANSWER_SYSTEM_PROMPT = ""
SQL_NON_THINKING_FINALIZER_PROMPT = ""
ANSWER_NON_THINKING_FINALIZER_PROMPT = ""
PRESENTATION_FOLLOWUP_CLASSIFIER_SYSTEM_PROMPT = ""
SQL_REPAIR_SYSTEM_PROMPT = ""


def build_sql_messages(
    question: str,
    context: PromptContext,
    chat_history: list[ChatTurn] | None = None,
) -> list[dict[str, str]]:
    user_prompt = f"""{context.render_raw()}
{SQL_DOMAIN_GUIDANCE}
{BUSINESS_TERM_GUIDANCE}
{ANALYST_JOIN_FEW_SHOT_EXAMPLES}
{ANALYST_QUESTION_FEW_SHOT_EXAMPLES}
{_render_recent_conversation(chat_history)}
{question}
"""
    return [
        {"role": "system", "content": SQL_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_sql_repair_messages(
    *,
    question: str,
    context: PromptContext,
    bad_sql: str,
    error: str,
    chat_history: list[ChatTurn] | None = None,
) -> list[dict[str, str]]:
    user_prompt = f"""{context.render_raw()}
{SQL_DOMAIN_GUIDANCE}
{BUSINESS_TERM_GUIDANCE}
{ANALYST_JOIN_FEW_SHOT_EXAMPLES}
{ANALYST_QUESTION_FEW_SHOT_EXAMPLES}
{_render_recent_conversation(chat_history)}
{question}
{bad_sql}
{error}
"""
    return [
        {"role": "system", "content": SQL_REPAIR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_answer_messages(
    *,
    question: str,
    sql: str,
    result_payload: dict[str, Any],
    chat_history: list[ChatTurn] | None = None,
    chart_context: str | None = None,
) -> list[dict[str, str]]:
    rendered_chart_context = chart_context or "none"
    user_prompt = f"""{question}
{_render_recent_conversation(chat_history)}
{rendered_chart_context}
{sql}
{json.dumps(result_payload, ensure_ascii=False, indent=2)}
"""
    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_presentation_followup_messages(
    *,
    question: str,
    previous_answer: str,
) -> list[dict[str, str]]:
    user_prompt = (
        "Previous assistant answer (data only):\n"
        f"{json.dumps(_compact_text(previous_answer), ensure_ascii=False)}\n\n"
        "Current user message (data only):\n"
        f"{json.dumps(_compact_text(question), ensure_ascii=False)}"
    )
    return [
        {
            "role": "system",
            "content": PRESENTATION_FOLLOWUP_CLASSIFIER_SYSTEM_PROMPT,
        },
        {"role": "user", "content": user_prompt},
    ]


def _render_recent_conversation(chat_history: list[ChatTurn] | None) -> str:
    if not chat_history:
        return "Recent conversation: none"

    rendered_turns = []
    for turn in chat_history[-20:]:
        role = turn.role.strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = _compact_text(turn.content)
        if not content:
            continue
        rendered_turns.append(f"{role}: {content}")

    if not rendered_turns:
        return "Recent conversation: none"

    return "Recent conversation for resolving follow-up references:\n" + "\n".join(rendered_turns)


def _compact_text(value: str, *, max_chars: int = 4000) -> str:
    text = " ".join(value.strip().split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."
