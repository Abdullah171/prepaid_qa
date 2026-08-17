"""End-to-end natural-language to SQL and analytical answer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import logging
from pathlib import Path
import time
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
from performance_planning_qa.cancellation import AnalysisCancelled, CancellationToken
from performance_planning_qa.config import AppSettings, load_settings
from performance_planning_qa.context_loader import PromptContext, load_prompt_context
from performance_planning_qa.csv_export import (
    CSVExportSpec,
    CSV_READY_TEXT,
    append_csv_message,
    build_csv_export_spec,
    build_query_result_csv_export_spec,
    build_ready_csv_export_spec,
    extract_displayed_table,
    has_explicit_csv_request,
    has_offered_csv,
    is_csv_followup,
    strip_embedded_csv_dump,
)
from performance_planning_qa.database import DatabaseQueryError, QueryResult, TeradataClient
from performance_planning_qa.diagnostics import (
    diagnostic_event,
    diagnostic_exception,
    diagnostic_failure_summary,
)
from performance_planning_qa.llm import (
    LLMContextWindowExceededError,
    LiteLLMClient,
    extract_json_object,
)
from performance_planning_qa.prompt_logger import PromptLogger
from performance_planning_qa.prompts import (
    ANSWER_NON_THINKING_FINALIZER_PROMPT,
    ChatTurn,
    SQL_NON_THINKING_FINALIZER_PROMPT,
    build_answer_messages,
    build_presentation_followup_messages,
    build_sql_messages,
    build_sql_repair_messages,
)
from performance_planning_qa.result_formatting import compact_result_payload_for_llm
from performance_planning_qa.sql_safety import (
    SQLSafetyError,
    SQLValidationResult,
    validate_readonly_sql,
)
from performance_planning_qa.user_messages import ANALYSIS_UNAVAILABLE_MESSAGE


logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]
ReasoningCallback = Callable[[str], None]


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
    csv_export: CSVExportSpec | None = None
    prompt_log_paths: tuple[Path, ...] = ()
    dry_run: bool = False
    error: str | None = None
    error_stage: str | None = None
    answer_generation_limited: bool = False

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
            "csv_export": self.csv_export.to_payload() if self.csv_export else None,
            "error": self.error,
            "error_stage": self.error_stage,
            "answer_generation_limited": self.answer_generation_limited,
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
        self._reasoning_callback: ReasoningCallback | None = None
        self._cancellation_token: CancellationToken | None = None
        self._enable_thinking = True
        self._diagnostic_request_id: str | None = None

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
        enable_thinking: bool = True,
        chat_history: list[ChatTurn] | None = None,
        previous_result: dict[str, Any] | None = None,
        progress_callback: ProgressCallback | None = None,
        reasoning_callback: ReasoningCallback | None = None,
        cancellation_token: CancellationToken | None = None,
        diagnostic_request_id: str | None = None,
    ) -> PipelineResult:
        self._current_prompt_logs = []
        self._current_chat_history = chat_history or []
        self._progress_callback = progress_callback
        self._reasoning_callback = reasoning_callback
        self._cancellation_token = cancellation_token
        self._enable_thinking = enable_thinking
        self._diagnostic_request_id = diagnostic_request_id
        diagnostic_event(
            component="pipeline",
            stage="request",
            status="started",
            request_id=diagnostic_request_id,
            question_chars=len(question),
            history_turns=len(self._current_chat_history),
            dry_run=dry_run,
            thinking_enabled=enable_thinking,
        )
        self._report_progress("Fetching relevant information")
        if not dry_run:
            presentation_followup = self._presentation_followup_result(
                question,
                previous_result,
            )
            if presentation_followup is not None:
                if presentation_followup.chart is not None:
                    self._report_progress("Preparing the requested view")
                elif presentation_followup.csv_export is not None:
                    self._report_progress("Preparing the CSV file")
                else:
                    self._report_progress("Preparing the response")
                return presentation_followup

        self._report_progress("Reviewing the available data")
        generated = self.generate_sql(question, chat_history=self._current_chat_history)
        diagnostic_event(
            component="pipeline",
            stage="sql_generation_result",
            status="completed",
            request_id=self._diagnostic_request_id,
            has_sql=bool(generated.sql),
            sql_chars=len(generated.sql or ""),
            needs_clarification=generated.needs_clarification,
            has_direct_answer=bool(generated.direct_answer),
        )
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
        diagnostic_event(
            component="pipeline",
            stage="sql_validation",
            status="completed",
            request_id=self._diagnostic_request_id,
            tables=list(validation.table_references),
        )
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

        diagnostic_event(
            component="pipeline",
            stage="database_query",
            status="completed",
            request_id=self._diagnostic_request_id,
            row_count=executed.query_result.row_count,
            query_elapsed_ms=executed.query_result.elapsed_ms,
            columns=executed.query_result.columns,
        )

        inherited_intent, inherited_candidate, chart_context = (
            self._inherited_chart_context(question, previous_result)
        )
        self._report_progress("Analyzing the findings")
        try:
            answer_payload = self._answer_from_result(
                question,
                executed.validation.sql,
                executed.query_result,
                chart_context=chart_context,
            )
        except LLMContextWindowExceededError:
            return self._context_window_csv_result(
                question=question,
                executed=executed,
            )
        answer_payload = _normalize_answer_payload(answer_payload)
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
        effective_chart_intent = inherited_intent
        if (
            effective_chart_intent is None
            and detect_chart_intent(question) is None
            and not chart_output_suppressed(question)
        ):
            effective_chart_intent = _semantic_chart_intent_from_candidate(
                chart_candidate
            )
        chart = self._build_chart(
            question,
            executed.query_result,
            candidate=chart_candidate,
            inherited_intent=effective_chart_intent,
        )
        raw_answer = strip_embedded_csv_dump(answer_payload.get("answer"))
        csv_export = build_csv_export_spec(
            question,
            table=extract_displayed_table(raw_answer),
        )
        answer = append_csv_message(raw_answer, csv_export)
        diagnostic_event(
            component="pipeline",
            stage="final_answer",
            status="completed",
            request_id=self._diagnostic_request_id,
            answer_chars=len(answer or ""),
            has_chart=chart is not None,
            has_csv=csv_export is not None,
        )
        return PipelineResult(
            question=question,
            generated_sql=executed.generated,
            validation_tables=executed.validation.table_references,
            query_result=executed.query_result,
            answer=answer,
            chart=chart,
            csv_export=csv_export,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
        )

    def _context_window_csv_result(
        self,
        *,
        question: str,
        executed: SQLExecutionResult,
    ) -> PipelineResult:
        """Return successful query data when it is too large for answer generation."""

        assert executed.validation is not None
        assert executed.query_result is not None
        self._report_progress("Preparing the complete result as a CSV file")
        result = executed.query_result
        csv_export = build_query_result_csv_export_spec(
            question,
            columns=result.columns,
            row_count=result.row_count,
        )
        answer = (
            f"The query completed successfully and returned {result.row_count:,} rows, "
            "but that result is too large for the AI model to analyze in one response. "
            "The complete result is available below as a CSV file that opens in Excel. "
            "The SQL used to produce it is also shown below."
        )
        diagnostic_event(
            component="pipeline",
            stage="answer_context_fallback",
            status="completed",
            request_id=self._diagnostic_request_id,
            row_count=result.row_count,
            has_csv=csv_export is not None,
        )
        return PipelineResult(
            question=question,
            generated_sql=executed.generated,
            validation_tables=executed.validation.table_references,
            query_result=result,
            answer=answer,
            csv_export=csv_export,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
            answer_generation_limited=True,
        )

    def fork(self) -> NL2SQLPipeline:
        """Create request-local mutable state while sharing context and database."""

        return NL2SQLPipeline(
            self.settings,
            db_client=self.db,
            context=self.context,
        )

    def close(self, *, close_database: bool = True) -> None: # type: ignore
        try:
            if close_database:
                self.db.close()
        finally:
            self.llm.close()

    def _report_progress(self, message: str) -> None:
        self._check_cancelled()
        diagnostic_event(
            component="pipeline",
            stage=_diagnostic_stage_name(message),
            status="started",
            request_id=self._diagnostic_request_id,
            progress=message,
        )
        callback = self._progress_callback
        if callback is None:
            return
        try:
            callback(message)
        except Exception:
            # Progress reporting is best-effort and must never fail an analysis.
            logger.debug("Progress callback failed", exc_info=True)

    def _check_cancelled(self) -> None:
        if self._cancellation_token is not None:
            self._cancellation_token.raise_if_cancelled()

    def _presentation_followup_result(
        self,
        question: str,
        previous_result: dict[str, Any] | None,
    ) -> PipelineResult | None:
        """Understand arbitrary chart/CSV follow-ups before running new SQL."""

        if not isinstance(previous_result, dict):
            return None

        csv_was_offered = has_offered_csv(previous_result)
        chart_result = self._chart_followup_result(question, previous_result)
        if chart_result is not None:
            if csv_was_offered and (
                is_csv_followup(question, previous_result)
                or has_explicit_csv_request(question)
            ):
                return self._add_ready_csv(
                    chart_result,
                    previous_result,
                )
            return chart_result
        if csv_was_offered and is_csv_followup(
            question,
            previous_result,
        ):
            return self._ready_csv_followup_result(question, previous_result)

        has_rows = _query_result_from_payload(previous_result.get("query_result")) is not None
        if not has_rows and not csv_was_offered:
            return None

        intent, requested_type = self._classify_presentation_followup(
            question,
            previous_result,
        )
        if intent in {
            "chart_previous_result",
            "chart_and_csv_previous_result",
        } and has_rows:
            chart_result = self._chart_followup_result(
                question,
                previous_result,
                forced_intent=ChartIntent(
                    trigger="explicit",
                    requested_type=requested_type, # type: ignore
                ),
            )
            if (
                chart_result is not None
                and intent == "chart_and_csv_previous_result"
                and csv_was_offered
            ):
                return self._add_ready_csv(chart_result, previous_result)
            return chart_result
        if intent == "csv_previous_table" and csv_was_offered:
            return self._ready_csv_followup_result(question, previous_result)
        if intent == "decline_csv" and csv_was_offered:
            return PipelineResult(
                question=question,
                generated_sql=GeneratedSQL(sql=None),
                answer="No problem. Let me know if you need another format or analysis.",
                prompt_log_paths=tuple(self._current_prompt_logs),
                dry_run=False,
            )
        return None

    def _add_ready_csv(
        self,
        chart_result: PipelineResult,
        previous_result: dict[str, Any],
    ) -> PipelineResult:
        """Return a chart and the previously offered table as one response."""

        previous_export = previous_result.get("csv_export")
        csv_export = (
            build_ready_csv_export_spec(previous_export)
            if isinstance(previous_export, dict)
            else None
        )
        if csv_export is None:
            return chart_result
        answer = append_csv_message(chart_result.answer, csv_export)
        return replace(
            chart_result,
            answer=answer,
            csv_export=csv_export,
        )

    def _ready_csv_followup_result(
        self,
        question: str,
        previous_result: dict[str, Any],
    ) -> PipelineResult | None:
        """Promote the preceding displayed table to a ready CSV artifact."""

        if not has_offered_csv(previous_result):
            return None
        previous_export = previous_result.get("csv_export")
        if not isinstance(previous_export, dict):
            return None

        csv_export = build_ready_csv_export_spec(previous_export)
        if csv_export is None:
            return None
        query_result = _query_result_from_payload(previous_result.get("query_result"))
        return PipelineResult(
            question=question,
            generated_sql=GeneratedSQL(sql=_optional_str(previous_result.get("sql"))),
            validation_tables=_validation_tables_from_payload(previous_result),
            query_result=query_result,
            answer=CSV_READY_TEXT,
            csv_export=csv_export,
            prompt_log_paths=tuple(self._current_prompt_logs),
            dry_run=False,
        )

    def _classify_presentation_followup(
        self,
        question: str,
        previous_result: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Use the LLM for natural presentation requests and scope changes."""

        completion_options = {}
        if not self._enable_thinking:
            completion_options["enable_thinking"] = False
        try:
            payload = self.llm.complete_json(
                build_presentation_followup_messages(
                    question=question,
                    previous_answer=str(previous_result.get("answer") or ""),
                ),
                temperature=0.0,
                log_empty_response=False,
                reasoning_callback=None,
                cancellation_token=self._cancellation_token,
                **completion_options,
            )
        except AnalysisCancelled:
            raise
        except Exception as exc:
            # Classification is optional. Falling through lets the ordinary
            # analytical pipeline handle the message instead of failing chat.
            logger.debug(
                "Presentation follow-up classification was unavailable: %s",
                exc,
            )
            return "new_request", None

        intent = str(payload.get("intent") or "").strip().lower()
        if intent not in {
            "chart_previous_result",
            "chart_and_csv_previous_result",
            "csv_previous_table",
            "decline_csv",
            "new_request",
        }:
            return "new_request", None
        raw_chart_type = str(payload.get("chart_type") or "").strip().lower()
        chart_type = raw_chart_type if raw_chart_type in ALLOWED_CHART_TYPES else None
        return intent, chart_type

    def _chart_followup_result(
        self,
        question: str,
        previous_result: dict[str, Any] | None,
        *,
        forced_intent: ChartIntent | None = None,
    ) -> PipelineResult | None:
        """Reuse the preceding rows for requests such as "make that a bar chart"."""

        if not isinstance(previous_result, dict) or (
            forced_intent is None and not is_chart_only_followup(question)
        ):
            return None

        query_result = _query_result_from_payload(previous_result.get("query_result"))
        if query_result is None:
            return None

        previous_chart = previous_result.get("chart")
        candidate: dict[str, Any] | None = (
            dict(previous_chart) if isinstance(previous_chart, dict) else None
        )
        if forced_intent is not None and forced_intent.requested_type is not None:
            candidate = candidate or {}
            candidate["type"] = forced_intent.requested_type
        chart = self._build_chart(
            question,
            query_result,
            candidate=candidate,
            inherited_intent=forced_intent,
        )
        if chart is None:
            return None

        sql = _optional_str(previous_result.get("sql"))
        generated = GeneratedSQL(sql=sql)
        return PipelineResult(
            question=question,
            generated_sql=generated,
            validation_tables=_validation_tables_from_payload(previous_result),
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
                diagnostic_event(
                    component="pipeline",
                    stage="sql_validation",
                    status="retrying" if attempt < attempts else "failed",
                    request_id=self._diagnostic_request_id,
                    level=logging.WARNING if attempt < attempts else logging.ERROR,
                    attempt=attempt + 1,
                    max_attempts=attempts + 1,
                    error=str(exc),
                )
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
            query_result = self._execute_select(validation.sql)
        except DatabaseQueryError as exc:
            diagnostic_event(
                component="pipeline",
                stage="database_query",
                status="repairing",
                request_id=self._diagnostic_request_id,
                level=logging.WARNING,
                error=str(exc),
            )
            self._check_cancelled()
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
                result = self._execute_select(validation.sql)
                return SQLExecutionResult(
                    generated=current,
                    validation=validation,
                    query_result=result,
                )
            except (DatabaseQueryError, SQLSafetyError) as exc:
                self._check_cancelled()
                last_error = str(exc)
                error = str(exc)
        return SQLExecutionResult(
            generated=current,
            error=f"SQL execution failed after repair attempt: {last_error or error}",
        )

    def _execute_select(self, sql: str) -> QueryResult:
        if isinstance(self.db, TeradataClient):
            return self.db.execute_select(
                sql,
                cancellation_token=self._cancellation_token,
            )
        # Preserve compatibility with lightweight injected database clients.
        self._check_cancelled()
        result = self.db.execute_select(sql)
        self._check_cancelled()
        return result

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
        diagnostic_event(
            component="pipeline",
            stage=f"sql_{phase}",
            status="failed",
            request_id=self._diagnostic_request_id,
            level=logging.ERROR,
            error=cleaned_error or "No error detail was returned",
        )
        diagnostic_failure_summary(
            component="pipeline",
            request_id=self._diagnostic_request_id,
            failed_step=(
                "SQL validation/repair"
                if phase == "validation"
                else "Database execution/SQL repair"
            ),
            error=cleaned_error or "No error detail was returned",
            generated_sql=generated.sql,
        )
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
            error_stage=phase,
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
        print("Repaied SQL = ", repaired)
        return repaired

    def _answer_from_result(
        self,
        question: str,
        sql: str,
        result: QueryResult,
        *,
        chart_context: str | None = None,
    ) -> dict[str, Any]:
        payload = compact_result_payload_for_llm(result.to_payload())

        # print("Sql query result. = ", payload, flush=True)
        print(
            "Calling answer-generation LLM "
            f"(stream={self.settings.llm.stream})...",
            flush=True,
        )

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
        print(
            "Final LLM answer response:\n",
            json.dumps(final_llm_response, ensure_ascii=False, indent=2),
            flush=True,
        )
        return final_llm_response

    def _complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        phase: str,
        temperature: float,
    ) -> dict[str, Any]:
        # self.prompt_logger.log(phase=phase, messages=messages, temperature=temperature)  # DEBUG: comment out this line to stop writing LLM input files.
        is_answer_generation = phase == "answer_generation"
        fallback_key = "answer" if is_answer_generation else "direct_answer"
        reasoning_fallback_instruction = (
            ANSWER_NON_THINKING_FINALIZER_PROMPT
            if is_answer_generation
            else SQL_NON_THINKING_FINALIZER_PROMPT
        )
        completion_options = {}
        if not self._enable_thinking:
            completion_options["enable_thinking"] = False
        if (
            is_answer_generation
            and self.settings.llm.provider == "glm"
            and self._enable_thinking
        ):
            completion_options["reasoning_effort"] = "low"
        started = time.monotonic()
        diagnostic_event(
            component="pipeline",
            stage=phase,
            status="started",
            request_id=self._diagnostic_request_id,
            provider=self.settings.llm.provider,
            model=self.settings.llm.model,
            streaming=self.settings.llm.stream,
        )
        try:
            payload = self.llm.complete_json(
                messages,
                temperature=temperature,
                fallback_key=fallback_key,
                reasoning_callback=self._reasoning_callback,
                cancellation_token=self._cancellation_token,
                reasoning_fallback_instruction=reasoning_fallback_instruction,
                **completion_options,
            )
        except AnalysisCancelled:
            diagnostic_event(
                component="pipeline",
                stage=phase,
                status="cancelled",
                request_id=self._diagnostic_request_id,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except Exception as exc:
            diagnostic_exception(
                component="pipeline",
                stage=phase,
                request_id=self._diagnostic_request_id,
                error=exc,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        diagnostic_event(
            component="pipeline",
            stage=phase,
            status="completed",
            request_id=self._diagnostic_request_id,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            response_fields=sorted(payload),
        )
        return payload


def _generated_sql_from_payload(payload: dict[str, Any]) -> GeneratedSQL:
    return GeneratedSQL(
        sql=_optional_str(payload.get("sql")),
        needs_clarification=bool(payload.get("needs_clarification", False)),
        clarifying_question=_optional_str(payload.get("clarifying_question")),
        direct_answer=_optional_str(payload.get("direct_answer")),
    )


def _semantic_chart_intent_from_candidate(candidate: Any) -> ChartIntent | None:
    """Treat a complete answer-model chart plan as semantic chart intent.

    The answer model sees the original user wording and can understand requests
    that the conservative local detector does not recognize.  Requiring the
    complete documented plan shape keeps an incidental or malformed ``chart``
    value from turning an ordinary answer into a visualization.  The plan still
    contains field references only; :func:`build_chart_spec` validates those
    references and copies every plotted value from the current query result.
    """

    if not isinstance(candidate, dict):
        return None
    chart_type = candidate.get("type")
    x_field = candidate.get("x")
    y_fields = candidate.get("y")
    if (
        not isinstance(chart_type, str)
        or chart_type.strip().lower() not in ALLOWED_CHART_TYPES
        or not isinstance(x_field, str)
        or not x_field.strip()
        or not isinstance(y_fields, (list, tuple))
        or not y_fields
        or not all(isinstance(field, str) and field.strip() for field in y_fields)
    ):
        return None
    return ChartIntent(trigger="explicit")


def _normalize_answer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Unwrap an answer when a provider returns the JSON object as text."""

    normalized = dict(payload)
    for _ in range(2):
        raw_answer = normalized.get("answer")
        if not isinstance(raw_answer, str):
            break
        candidate = raw_answer.strip()
        if not candidate:
            break

        nested: Any = None
        try:
            decoded = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            try:
                nested = extract_json_object(candidate)
            except (TypeError, ValueError):
                break
        else:
            if isinstance(decoded, str):
                try:
                    nested = extract_json_object(decoded)
                except (TypeError, ValueError):
                    break
            else:
                nested = decoded

        if not isinstance(nested, dict) or not isinstance(nested.get("answer"), str):
            break
        # Prefer the actual nested answer/chart while retaining any outer
        # application fields a provider did not repeat.
        normalized.update(nested)
    return normalized


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


def _validation_tables_from_payload(value: dict[str, Any]) -> tuple[str, ...]:
    raw_tables = value.get("validation_tables")
    if not isinstance(raw_tables, (list, tuple)):
        return ()
    return tuple(str(table) for table in raw_tables if str(table).strip())


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


def _diagnostic_stage_name(message: str) -> str:
    """Turn a user-facing progress label into a stable log stage name."""

    return "_".join(str(message).strip().lower().split()) or "unknown"


def _sql_failure_message(error: str | None, *, phase: str) -> tuple[str, bool]:
    if not error:
        return ANALYSIS_UNAVAILABLE_MESSAGE, True

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
            "I couldn't match part of the question confidently to the available "
            "information. Please clarify the metric, category, or filter you want and "
            "ask again.",
            True,
        )

    if any(token in lowered for token in ("date", "timestamp", "invalid time")):
        return (
            "I couldn't determine the reporting period confidently. Please specify the "
            "exact date, month, year, or date range and ask again.",
            True,
        )

    if any(token in lowered for token in ("ambiguous", "ambig")):
        return (
            "Part of the question could have more than one meaning. Please clarify the "
            "metric and how you want it grouped, then ask again.",
            True,
        )

    if any(token in lowered for token in ("timeout", "spool", "memory", "exceeded")):
        return (
            "I wasn't able to fetch the information because the request is too broad. "
            "Please narrow the date range, customer segment, filters, or grouping and "
            "ask again.",
            True,
        )

    if any(token in lowered for token in ("permission", "access", "authorized", "logon")):
        return ANALYSIS_UNAVAILABLE_MESSAGE, False

    if phase == "validation":
        return ANALYSIS_UNAVAILABLE_MESSAGE, True

    return ANALYSIS_UNAVAILABLE_MESSAGE, False


def _scoped_direct_answer() -> str:
    return (
        "Hi. I can help with analytical questions about the provided performance planning "
        "database schema, including postpaid base, sales, churn, and monthly revenue tables."
    )
