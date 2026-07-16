"""End-to-end natural-language to SQL and analytical answer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import logging
from pathlib import Path
from typing import Any, Callable

from performance_planning_qa.charting import (
    ALLOWED_CHART_TYPES,
    ChartIntent,
    ChartSpec,
    build_chart_spec,
    chart_output_suppressed,
    detect_chart_intent,
    is_anaphoric_chart_followup,
    is_chart_only_followup,
)
from performance_planning_qa.config import AppSettings, load_settings
from performance_planning_qa.context_loader import PromptContext, load_prompt_context
from performance_planning_qa.database import DatabaseQueryError, QueryResult, TeradataClient
from performance_planning_qa.llm import LiteLLMClient
from performance_planning_qa.prompt_logger import PromptLogger
from performance_planning_qa.prompts import (
    ChatTurn,
    build_answer_messages,
    build_sql_messages,
    build_sql_repair_messages,
)
from performance_planning_qa.sql_safety import (
    SQLSafetyError,
    SQLValidationResult,
    validate_readonly_sql,
)


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str | None
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
    chart: ChartSpec | None = None
    prompt_log_paths: tuple[Path, ...] = ()
    dry_run: bool = False
    error: str | None = None

    @property
    def sql(self) -> str | None:
        return self.generated_sql.sql

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "sql": self.generated_sql.sql,
            "needs_clarification": self.generated_sql.needs_clarification,
            "clarifying_question": self.generated_sql.clarifying_question,
            "direct_answer": self.generated_sql.direct_answer,
            "validation_tables": list(self.validation_tables),
            "dry_run": self.dry_run,
            "answer": self.answer,
            "chart": self.chart.to_payload() if self.chart else None,
            "error": self.error,
            "prompt_log_paths": [str(path) for path in self.prompt_log_paths],
            "query_result": self.query_result.to_payload() if self.query_result else None,
        }


@dataclass(frozen=True)
class SQLPreparationResult:
    generated: GeneratedSQL
    validation: SQLValidationResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class SQLExecutionResult:
    generated: GeneratedSQL
    validation: SQLValidationResult | None = None
    query_result: QueryResult | None = None
    error: str | None = None


class NL2SQLPipeline:
    def __init__(
        self,
        settings: AppSettings,
        *,
        llm_client: LiteLLMClient | None = None,
        db_client: TeradataClient | None = None,
        context: PromptContext | None = None,
    ):
        self.settings = settings
        self.context = context or load_prompt_context(settings.schema_path, settings.sample_data_dir)
        self.llm = llm_client or LiteLLMClient(settings.llm)
        self.db = db_client or TeradataClient(settings.teradata)
        self.prompt_logger = PromptLogger(settings.prompt_log, settings.llm)
        self._current_prompt_logs: list[Path] = []
        self._current_chat_history: list[ChatTurn] = []
        self._progress_callback: ProgressCallback | None = None

    @classmethod
    def from_env(cls) -> NL2SQLPipeline:
        return cls(load_settings())

    def generate_sql(
        self,
        question: str,
        *,
        chat_history: list[ChatTurn] | None = None,
    ) -> GeneratedSQL:
        payload = self._complete_json(
            build_sql_messages(question, self.context, chat_history=chat_history),
            phase="sql_generation",
            temperature=self.settings.llm.sql_temperature,
        )
        return _generated_sql_from_payload(payload)

    def ask(
        self,
        question: str,
        *,
        dry_run: bool = False,
        chat_history: list[ChatTurn] | None = None,
        previous_result: dict[str, Any] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        self._current_prompt_logs = []
        self._current_chat_history = chat_history or []
        self._progress_callback = progress_callback
        self._report_progress("Fetching relevant information")
        if not dry_run:
            chart_followup = self._chart_followup_result(question, previous_result)
            if chart_followup is not None:
                self._report_progress("Preparing the requested view")
                return chart_followup

        self._report_progress("Reviewing the available data")
        generated = self.generate_sql(question, chat_history=self._current_chat_history)
        direct_result = self._direct_generated_result(
            question=question,
            generated=generated,
            dry_run=dry_run,
            allow_missing_sql_fallback=True,
        )
        if direct_result is not None:
            return direct_result

        self._report_progress("Checking the information")
        prepared = self._validate_or_repair(question, generated)
        direct_result = self._direct_generated_result(
            question=question,
            generated=prepared.generated,
            dry_run=dry_run,
            allow_missing_sql_fallback=False,
        )
        if direct_result is not None:
            return direct_result
        if prepared.validation is None:
            return self._sql_failure_result(
                question=question,
                generated=prepared.generated,
                error=prepared.error,
                dry_run=dry_run,
                phase="validation",
            )

        generated = prepared.generated
        validation = prepared.validation
        if dry_run:
            return PipelineResult(
                question=question,
                generated_sql=generated,
                validation_tables=validation.table_references,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=True,
            )

        self._report_progress("Gathering the requested results")
        executed = self._execute_or_repair(
            question=question,
            generated=generated,
            validation=validation,
        )
        direct_result = self._direct_generated_result(
            question=question,
            generated=executed.generated,
            dry_run=False,
            allow_missing_sql_fallback=False,
        )
        if direct_result is not None:
            return direct_result
        if executed.validation is None or executed.query_result is None:
            return self._sql_failure_result(
                question=question,
                generated=executed.generated,
                error=executed.error,
                dry_run=False,
                phase="execution",
            )

        inherited_intent, inherited_candidate, chart_context = (
            self._inherited_chart_context(question, previous_result)
        )
        self._report_progress("Analyzing the findings")
        answer_payload = self._answer_from_result(
            question,
            executed.validation.sql,
            executed.query_result,
            chart_context=chart_context,
        )
        answer_candidate = answer_payload.get("chart")
        if inherited_candidate is not None:
            merged_candidate = (
                dict(answer_candidate) if isinstance(answer_candidate, dict) else {}
            )
            # A strong "same" continuation keeps the preceding rendered type.
            # Current explicit type requests never reach the inheritance path.
            merged_candidate["type"] = inherited_candidate["type"]
            chart_candidate: Any = merged_candidate
        else:
            chart_candidate = answer_candidate
        self._report_progress("Preparing the final answer")
        chart = self._build_chart(
            question,
            executed.query_result,
            candidate=chart_candidate,
            inherited_intent=inherited_intent,
        )
        return PipelineResult(
            question=question,
            generated_sql=executed.generated,
            validation_tables=executed.validation.table_references,
            query_result=executed.query_result,
            answer=str(answer_payload.get("answer") or "").strip(),
            chart=chart,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
        )

    def close(self) -> None:
        try:
            self.db.close()
        finally:
            self.llm.close()

    def _report_progress(self, message: str) -> None:
        callback = self._progress_callback
        if callback is None:
            return
        try:
            callback(message)
        except Exception:
            # Progress reporting is best-effort and must never fail an analysis.
            logger.debug("Progress callback failed", exc_info=True)

    def _chart_followup_result(
        self,
        question: str,
        previous_result: dict[str, Any] | None,
    ) -> PipelineResult | None:
        """Reuse the preceding rows for requests such as "make that a bar chart"."""

        if not is_chart_only_followup(question) or not isinstance(previous_result, dict):
            return None

        query_result = _query_result_from_payload(previous_result.get("query_result"))
        if query_result is None:
            return None

        previous_chart = previous_result.get("chart")
        candidate = previous_chart if isinstance(previous_chart, dict) else None
        chart = self._build_chart(question, query_result, candidate=candidate)
        if chart is None:
            return None

        sql = _optional_str(previous_result.get("sql"))
        generated = GeneratedSQL(sql=sql)
        raw_validation_tables = previous_result.get("validation_tables")
        if not isinstance(raw_validation_tables, (list, tuple)):
            raw_validation_tables = []
        validation_tables = tuple(
            str(table)
            for table in raw_validation_tables
            if str(table).strip()
        )
        return PipelineResult(
            question=question,
            generated_sql=generated,
            validation_tables=validation_tables,
            query_result=query_result,
            answer=f"Here’s the previous result as a {chart.type} chart.",
            chart=chart,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
        )

    def _build_chart(
        self,
        question: str,
        result: QueryResult,
        *,
        candidate: Any,
        inherited_intent: ChartIntent | None = None,
    ) -> ChartSpec | None:
        """Validate an optional model plan; chart failure must not fail the answer."""

        try:
            if inherited_intent is not None:
                return build_chart_spec(
                    question,
                    result,
                    candidate=candidate,
                    inherited_intent=inherited_intent,
                )
            return build_chart_spec(question, result, candidate=candidate)
        except Exception:
            logger.exception("Optional chart generation failed")
            return None

    def _inherited_chart_context(
        self,
        question: str,
        previous_result: dict[str, Any] | None,
    ) -> tuple[ChartIntent | None, dict[str, str] | None, str | None]:
        """Carry chart intent across restated analyses and clarification replies."""

        if not isinstance(previous_result, dict):
            return None, None, None

        if is_anaphoric_chart_followup(question):
            previous_chart = previous_result.get("chart")
            if isinstance(previous_chart, dict):
                chart_type = str(previous_chart.get("type") or "").strip().lower()
                if chart_type in ALLOWED_CHART_TYPES:
                    raw_trigger = str(
                        previous_chart.get("trigger") or "explicit"
                    ).strip().lower()
                    trigger = "trend" if raw_trigger == "trend" else "explicit"
                    intent = ChartIntent(trigger=trigger)
                    candidate = {"type": chart_type}
                    context = (
                        "The current question is a strong analytical continuation "
                        f"of the immediately preceding {chart_type} chart. Return a "
                        "chart plan for the new result when compatible, using only "
                        "its new fields and a new title."
                    )
                    return intent, candidate, context

        if (
            previous_result.get("needs_clarification") is True
            and detect_chart_intent(question) is None
            and not chart_output_suppressed(question)
        ):
            original_question = str(previous_result.get("question") or "").strip()
            original_intent = detect_chart_intent(original_question)
            if original_intent is not None:
                candidate = (
                    {"type": original_intent.requested_type}
                    if original_intent.requested_type is not None
                    else None
                )
                context = (
                    "The current answer resolves a clarification requested for the "
                    "immediately preceding visualization question. Return a chart "
                    "plan for the new result using only its fields and a new title."
                )
                return original_intent, candidate, context

        return None, None, None

    def _validate_or_repair(self, question: str, generated: GeneratedSQL) -> SQLPreparationResult:
        attempts = max(self.settings.sql_repair_attempts, 0)
        last_error: str | None = None
        current = generated
        for attempt in range(attempts + 1):
            if _has_direct_user_response(current):
                return SQLPreparationResult(generated=current)
            if not current.sql:
                return SQLPreparationResult(generated=current, error="LLM did not return SQL.")
            try:
                validation = validate_readonly_sql(current.sql or "")
                return SQLPreparationResult(generated=current, validation=validation)
            except SQLSafetyError as exc:
                last_error = str(exc)
                if attempt >= attempts:
                    break
                current = self._repair_sql(
                    question=question,
                    generated=current,
                    error=str(exc),
                )
        return SQLPreparationResult(
            generated=current,
            error=f"Generated SQL failed safety validation: {last_error}",
        )

    def _execute_or_repair(
        self,
        *,
        question: str,
        generated: GeneratedSQL,
        validation: SQLValidationResult,
    ) -> SQLExecutionResult:
        try:
            query_result = self.db.execute_select(validation.sql)
        except DatabaseQueryError as exc:
            return self._repair_after_database_error(
                question=question,
                generated=generated,
                error=str(exc),
            )
        return SQLExecutionResult(
            generated=generated,
            validation=validation,
            query_result=query_result,
        )

    def _repair_after_database_error(
        self,
        *,
        question: str,
        generated: GeneratedSQL,
        error: str,
    ) -> SQLExecutionResult:
        last_error = error
        current = generated
        for _ in range(max(self.settings.sql_repair_attempts, 1)):
            current = self._repair_sql(question=question, generated=current, error=error)
            if _has_direct_user_response(current):
                return SQLExecutionResult(generated=current, error=last_error)
            if not current.sql:
                return SQLExecutionResult(generated=current, error=last_error)
            try:
                validation = validate_readonly_sql(current.sql or "")
                result = self.db.execute_select(validation.sql)
                return SQLExecutionResult(
                    generated=current,
                    validation=validation,
                    query_result=result,
                )
            except (DatabaseQueryError, SQLSafetyError) as exc:
                last_error = str(exc)
                error = str(exc)
        return SQLExecutionResult(
            generated=current,
            error=f"SQL execution failed after repair attempt: {last_error or error}",
        )

    def _direct_generated_result(
        self,
        *,
        question: str,
        generated: GeneratedSQL,
        dry_run: bool,
        allow_missing_sql_fallback: bool,
    ) -> PipelineResult | None:
        if generated.needs_clarification:
            answer = generated.clarifying_question or _default_clarifying_question()
            generated = replace(generated, clarifying_question=answer)
            return PipelineResult(
                question=question,
                generated_sql=generated,
                answer=answer,
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
        if allow_missing_sql_fallback and not generated.sql:
            fallback = _scoped_direct_answer()
            generated = replace(generated, direct_answer=fallback)
            return PipelineResult(
                question=question,
                generated_sql=generated,
                answer=fallback,
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=dry_run,
            )
        return None

    def _sql_failure_result(
        self,
        *,
        question: str,
        generated: GeneratedSQL,
        error: str | None,
        dry_run: bool,
        phase: str,
    ) -> PipelineResult:
        cleaned_error = _sanitize_error(error)
        answer, needs_clarification = _sql_failure_message(cleaned_error, phase=phase)
        if needs_clarification:
            generated = replace(
                generated,
                needs_clarification=True,
                clarifying_question=answer,
                direct_answer=None,
            )
        return PipelineResult(
            question=question,
            generated_sql=generated,
            answer=answer,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=dry_run,
            error=cleaned_error,
        )

    def _repair_sql(self, *, question: str, generated: GeneratedSQL, error: str) -> GeneratedSQL:
        self._report_progress("Refining the analysis")
        payload = self._complete_json(
            build_sql_repair_messages(
                question=question,
                context=self.context,
                bad_sql=generated.sql or "",
                error=error,
                chat_history=self._current_chat_history,
            ),
            phase="sql_repair",
            temperature=self.settings.llm.sql_temperature,
        )
        repaired = _generated_sql_from_payload(payload)
        return repaired

    def _answer_from_result(
        self,
        question: str,
        sql: str,
        result: QueryResult,
        *,
        chart_context: str | None = None,
    ) -> dict[str, Any]:
        payload = result.to_payload()

        # print("Sql query result. = ", payload)

        final_llm_response = self._complete_json(
            build_answer_messages(
                question=question,
                sql=sql,
                result_payload=payload,
                chat_history=self._current_chat_history,
                chart_context=chart_context,
            ),
            phase="answer_generation",
            temperature=self.settings.llm.answer_temperature,
        )
        # print("Final LLM answer response:\n", json.dumps(final_llm_response, ensure_ascii=False, indent=2))
        return final_llm_response

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
        is_answer_generation = phase == "answer_generation"
        fallback_key = "answer" if is_answer_generation else "direct_answer"
        max_tokens = (
            self.settings.llm.answer_max_tokens
            if is_answer_generation
            else self.settings.llm.sql_max_tokens
        )
        return self.llm.complete_json(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback_key=fallback_key,
        )


def _generated_sql_from_payload(payload: dict[str, Any]) -> GeneratedSQL:
    return GeneratedSQL(
        sql=_optional_str(payload.get("sql")),
        needs_clarification=bool(payload.get("needs_clarification", False)),
        clarifying_question=_optional_str(payload.get("clarifying_question")),
        direct_answer=_optional_str(payload.get("direct_answer")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _query_result_from_payload(value: Any) -> QueryResult | None:
    """Rehydrate persisted rows for a chart-only follow-up without re-querying."""

    if not isinstance(value, dict):
        return None
    raw_rows = value.get("rows")
    if not isinstance(raw_rows, list):
        return None
    rows = [dict(row) for row in raw_rows if isinstance(row, dict)]
    if not rows:
        return None

    raw_columns = value.get("columns")
    if isinstance(raw_columns, list):
        columns = [str(column) for column in raw_columns if str(column).strip()]
    else:
        columns = []
    if not columns:
        columns = list(dict.fromkeys(str(key) for row in rows for key in row))
    if not columns:
        return None

    try:
        elapsed_ms = max(0, int(value.get("elapsed_ms") or 0))
    except (TypeError, ValueError):
        elapsed_ms = 0
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        elapsed_ms=elapsed_ms,
    )


def _has_direct_user_response(generated: GeneratedSQL) -> bool:
    return generated.needs_clarification or bool(generated.direct_answer)


def _default_clarifying_question() -> str:
    return "Please clarify the metric, time period, and filters you want analyzed."


def _sanitize_error(error: str | None) -> str | None:
    if error is None:
        return None
    text = " ".join(str(error).split())
    if not text:
        return None
    max_length = 600
    if len(text) > max_length:
        return f"{text[:max_length].rstrip()}..."
    return text


def _sql_failure_message(error: str | None, *, phase: str) -> tuple[str, bool]:
    if not error:
        return (
            "I could not build a valid SQL query for that question. Please clarify the "
            "metric, time period, and filters you want analyzed.",
            True,
        )

    lowered = error.lower()
    if any(
        token in lowered
        for token in (
            "column",
            "field",
            "object does not exist",
            "table",
            "not found",
            "does not exist",
            "invalid name",
            "unrecognized",
        )
    ):
        return (
            "I could not execute the query because the database rejected a generated "
            "table or field reference. Please clarify the exact metric, dimension, or "
            "filter you want using the available performance planning data.",
            True,
        )

    if any(token in lowered for token in ("date", "timestamp", "invalid time")):
        return (
            "I could not execute the query because the database rejected a date or "
            "time expression. Please clarify the exact date, month, year, or date "
            "range you want analyzed.",
            True,
        )

    if any(token in lowered for token in ("ambiguous", "ambig")):
        return (
            "I could not execute the query because part of the generated SQL was "
            "ambiguous. Please clarify the metric and grouping you want.",
            True,
        )

    if any(token in lowered for token in ("timeout", "spool", "memory", "exceeded")):
        return (
            "I could not execute the query after the repair attempt because it still "
            "looks too broad or expensive for the database. Please narrow the date "
            "range, filters, or grouping.",
            True,
        )

    if any(token in lowered for token in ("permission", "access", "authorized", "logon")):
        return (
            "The database rejected the query after the repair attempt because of an "
            f"access or connection issue: {error}",
            False,
        )

    if phase == "validation":
        return (
            "I could not produce a SQL query that passed the read-only safety checks "
            "after the repair attempt. Please rephrase the question with a clear "
            "metric, time period, and filters.",
            True,
        )

    return (
        "I could not execute a valid SQL query after the repair attempt. Database "
        f"error: {error}",
        False,
    )


def _scoped_direct_answer() -> str:
    return (
        "Hi. I can help with analytical questions about the provided performance planning "
        "database schema, including postpaid base, sales, churn, and monthly revenue tables."
    )
