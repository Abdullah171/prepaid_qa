"""Consistent, correlation-friendly diagnostics for one analysis request."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from typing import Any


LOGGER_NAME = "ppqa.diagnostics"
_logger = logging.getLogger(LOGGER_NAME)
_handler_lock = threading.Lock()


def _configure_logger() -> None:
    """Ensure diagnostic INFO entries are visible under Uvicorn and Streamlit."""

    with _handler_lock:
        has_diagnostic_handler = any(
            getattr(handler, "_ppqa_diagnostic_handler", False)
            for handler in _logger.handlers
        )
        if not has_diagnostic_handler:
            handler = logging.StreamHandler(sys.stderr)
            handler._ppqa_diagnostic_handler = True  # type: ignore[attr-defined]
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s [PPQA] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            _logger.addHandler(handler)
        configured_level = os.getenv("PPQA_LOG_LEVEL", "INFO").strip().upper()
        _logger.setLevel(getattr(logging, configured_level, logging.INFO))
        _logger.propagate = False


def diagnostic_event(
    *,
    component: str,
    stage: str,
    status: str,
    request_id: str | None = None,
    level: int = logging.INFO,
    **details: Any,
) -> None:
    """Print one structured event without model prompts, rows, or credentials."""

    _configure_logger()
    payload = {
        "request_id": request_id or "unassigned",
        "component": component,
        "stage": stage,
        "status": status,
        **{key: _safe_value(value) for key, value in details.items() if value is not None},
    }
    _logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def diagnostic_exception(
    *,
    component: str,
    stage: str,
    request_id: str | None,
    error: BaseException,
    **details: Any,
) -> None:
    """Print the failing stage, exception chain, and traceback."""

    _configure_logger()
    payload = {
        "request_id": request_id or "unassigned",
        "component": component,
        "stage": stage,
        "status": "failed",
        "error_type": type(error).__name__,
        "error": _safe_value(str(error)),
        **{key: _safe_value(value) for key, value in details.items() if value is not None},
    }
    exc_info = (type(error), error, error.__traceback__)
    _logger.error(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        exc_info=exc_info,
    )


def diagnostic_failure_summary(
    *,
    component: str,
    request_id: str | None,
    failed_step: str,
    error: str,
    generated_sql: str | None = None,
) -> None:
    """Print a prominent, human-readable summary for failures returned as results."""

    _configure_logger()
    sql_section = generated_sql.strip() if generated_sql and generated_sql.strip() else "<none>"
    _logger.error(
        "\n%s\n"
        "REQUEST FAILED\n"
        "request_id: %s\n"
        "component: %s\n"
        "failed_step: %s\n"
        "error: %s\n"
        "generated_or_repaired_sql:\n%s\n"
        "%s",
        "=" * 88,
        request_id or "unassigned",
        component,
        failed_step,
        error,
        sql_section,
        "=" * 88,
    )


def _safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 1_000:
            return f"{value[:1_000]}..."
        return value
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return _safe_value(str(value))
