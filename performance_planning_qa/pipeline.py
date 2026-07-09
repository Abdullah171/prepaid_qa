"""End-to-end natural-language to SQL and analytical answer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
from typing import Any

from performance_planning_qa.config import AppSettings, load_settings
from performance_planning_qa.context_loader import PromptContext, load_prompt_context
from performance_planning_qa.database import DatabaseQueryError, QueryResult, TeradataClient, to_jsonable
from performance_planning_qa.llm import MiniMaxClient
from performance_planning_qa.prompt_logger import PromptLogger
from performance_planning_qa.prompts import (
    build_answer_messages,
    build_sql_messages,
    build_sql_repair_messages,
)
from performance_planning_qa.sql_safety import SQLSafetyError, validate_readonly_sql


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str | None
    assumptions: list[str] = field(default_factory=list)
    explanation: str = ""
    result_intent: str = ""
    needs_clarification: bool = False
    clarifying_question: str | None = None
    direct_answer: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    question: str
    generated_sql: GeneratedSQL
    validation_tables: tuple[str, ...] = ()
    query_result: QueryResult | None = None
    answer: str | None = None
    key_points: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    prompt_log_paths: tuple[Path, ...] = ()
    dry_run: bool = False

    @property
    def sql(self) -> str | None:
        return self.generated_sql.sql

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "sql": self.generated_sql.sql,
            "assumptions": self.generated_sql.assumptions,
            "explanation": self.generated_sql.explanation,
            "result_intent": self.generated_sql.result_intent,
            "needs_clarification": self.generated_sql.needs_clarification,
            "clarifying_question": self.generated_sql.clarifying_question,
            "direct_answer": self.generated_sql.direct_answer,
            "validation_tables": list(self.validation_tables),
            "dry_run": self.dry_run,
            "answer": self.answer,
            "key_points": self.key_points,
            "caveats": self.caveats,
            "prompt_log_paths": [str(path) for path in self.prompt_log_paths],
            "query_result": self.query_result.to_payload() if self.query_result else None,
        }


class NL2SQLPipeline:
    def __init__(
        self,
        settings: AppSettings,
        *,
        llm_client: MiniMaxClient | None = None,
        db_client: TeradataClient | None = None,
        context: PromptContext | None = None,
    ):
        self.settings = settings
        self.context = context or load_prompt_context(settings.schema_path, settings.sample_data_dir)
        self.llm = llm_client or MiniMaxClient(settings.llm)
        self.db = db_client or TeradataClient(settings.teradata)
        self.prompt_logger = PromptLogger(settings.prompt_log, settings.llm)
        self._current_prompt_logs: list[Path] = []

    @classmethod
    def from_env(cls) -> NL2SQLPipeline:
        return cls(load_settings())

    def generate_sql(self, question: str) -> GeneratedSQL:
        payload = self._complete_json(
            build_sql_messages(question, self.context),
            phase="sql_generation",
            temperature=self.settings.llm.sql_temperature,
        )
        return _generated_sql_from_payload(payload)

    def ask(self, question: str, *, dry_run: bool = False, max_rows: int | None = None) -> PipelineResult:
        self._current_prompt_logs = []
        generated = self.generate_sql(question)
        if generated.needs_clarification:
            return PipelineResult(
                question=question,
                generated_sql=generated,
                answer=generated.clarifying_question,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=dry_run,
            )
        if generated.direct_answer:
            return PipelineResult(
                question=question,
                generated_sql=generated,
                answer=generated.direct_answer,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=dry_run,
            )
        if not generated.sql:
            fallback = _scoped_direct_answer()
            generated = replace(generated, direct_answer=fallback)
            return PipelineResult(
                question=question,
                generated_sql=generated,
                answer=fallback,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=dry_run,
            )

        generated, validation = self._validate_or_repair(question, generated)
        if dry_run:
            return PipelineResult(
                question=question,
                generated_sql=generated,
                validation_tables=validation.table_references,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=True,
            )

        effective_max_rows = max_rows or self.settings.query_max_rows
        try:
            query_result = self.db.execute_select(validation.sql, max_rows=effective_max_rows)
        except DatabaseQueryError as exc:
            generated, validation, query_result = self._repair_after_database_error(
                question=question,
                generated=generated,
                error=str(exc),
                max_rows=effective_max_rows,
            )

        answer_payload = self._answer_from_result(question, validation.sql, query_result)
        return PipelineResult(
            question=question,
            generated_sql=generated,
            validation_tables=validation.table_references,
            query_result=query_result,
            answer=str(answer_payload.get("answer") or "").strip(),
            key_points=_string_list(answer_payload.get("key_points")),
            caveats=_string_list(answer_payload.get("caveats")),
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
        )

    def close(self) -> None:
        self.db.close()

    def _validate_or_repair(self, question: str, generated: GeneratedSQL):
        attempts = max(self.settings.sql_repair_attempts, 0)
        last_error: Exception | None = None
        current = generated
        for attempt in range(attempts + 1):
            try:
                validation = validate_readonly_sql(current.sql or "")
                return current, validation
            except SQLSafetyError as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                current = self._repair_sql(
                    question=question,
                    generated=current,
                    error=str(exc),
                )
        raise RuntimeError(f"Generated SQL failed safety validation: {last_error}") from last_error

    def _repair_after_database_error(
        self,
        *,
        question: str,
        generated: GeneratedSQL,
        error: str,
        max_rows: int,
    ):
        last_error: Exception | None = None
        current = generated
        for _ in range(max(self.settings.sql_repair_attempts, 1)):
            current = self._repair_sql(question=question, generated=current, error=error)
            try:
                validation = validate_readonly_sql(current.sql or "")
                result = self.db.execute_select(validation.sql, max_rows=max_rows)
                return current, validation, result
            except (DatabaseQueryError, SQLSafetyError) as exc:
                last_error = exc
                error = str(exc)
        raise RuntimeError(f"SQL execution failed after repair attempt: {last_error or error}") from last_error

    def _repair_sql(self, *, question: str, generated: GeneratedSQL, error: str) -> GeneratedSQL:
        payload = self._complete_json(
            build_sql_repair_messages(
                question=question,
                context=self.context,
                bad_sql=generated.sql or "",
                error=error,
            ),
            phase="sql_repair",
            temperature=self.settings.llm.sql_temperature,
        )
        repaired = _generated_sql_from_payload(payload)
        if not repaired.assumptions:
            repaired = replace(repaired, assumptions=generated.assumptions)
        return repaired

    def _answer_from_result(self, question: str, sql: str, result: QueryResult) -> dict[str, Any]:
        payload = _bounded_result_payload(result, self.settings.answer_result_max_chars)
        return self._complete_json(
            build_answer_messages(question=question, sql=sql, result_payload=payload),
            phase="answer_generation",
            temperature=self.settings.llm.answer_temperature,
        )

    def _complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        phase: str,
        temperature: float,
    ) -> dict[str, Any]:
        # Prompt logging is disabled for normal runs. Keep this block available
        # for debugging, but do not write full schema/sample prompts by default.
        # record = self.prompt_logger.log(
        #     phase=phase,
        #     messages=messages,
        #     temperature=temperature,
        # )
        # if record is not None:
        #     self._current_prompt_logs.append(record.path)
        return self.llm.complete_json(messages, temperature=temperature)


def _generated_sql_from_payload(payload: dict[str, Any]) -> GeneratedSQL:
    return GeneratedSQL(
        sql=_optional_str(payload.get("sql")),
        assumptions=_string_list(payload.get("assumptions")),
        explanation=str(payload.get("explanation") or "").strip(),
        result_intent=str(payload.get("result_intent") or "").strip(),
        needs_clarification=bool(payload.get("needs_clarification", False)),
        clarifying_question=_optional_str(payload.get("clarifying_question")),
        direct_answer=_optional_str(payload.get("direct_answer")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _scoped_direct_answer() -> str:
    return (
        "Hi. I can help with analytical questions about the provided performance planning "
        "database schema, including postpaid base, sales, churn, and monthly revenue tables."
    )


def _bounded_result_payload(result: QueryResult, max_chars: int) -> dict[str, Any]:
    payload = result.to_payload()
    payload["rows"] = to_jsonable(payload["rows"])
    while True:
        encoded = json.dumps(payload, ensure_ascii=False, default=str)
        if len(encoded) <= max_chars or not payload["rows"]:
            payload["payload_truncated_for_llm"] = len(encoded) > max_chars
            return payload
        payload["rows"] = payload["rows"][: max(1, len(payload["rows"]) // 2)]
        payload["truncated"] = True
