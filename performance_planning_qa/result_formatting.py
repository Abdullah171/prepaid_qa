"""Prepare query results for compact, readable LLM analysis."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any, Mapping


_NUMBER_SCALES = (
    (Decimal("1000000000"), "B"),
    (Decimal("1000000"), "M"),
    (Decimal("1000"), "K"),
)

_IDENTIFIER_OR_PERIOD_PARTS = frozenset(
    {
        "CODE",
        "DATE",
        "DAY",
        "HOUR",
        "ID",
        "KEY",
        "MINUTE",
        "MONTH",
        "MSISDN",
        "NMBR",
        "NUM",
        "NUMBER",
        "RANK",
        "SECOND",
        "SEQ",
        "SEQUENCE",
        "TIME",
        "TIMESTAMP",
        "WEEK",
        "YEAR",
    }
)

_NUMBER_FORMAT_NOTE = (
    "Numeric measures use K = 1,000, M = 1,000,000, and B = 1,000,000,000. "
    "Compacted values are rounded to at most three decimal places."
)


def compact_result_payload_for_llm(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return an LLM-facing payload with large numeric measures abbreviated.

    The input is never mutated. Only values in result rows are candidates for
    compaction; payload metadata such as row count and elapsed time stays numeric.
    Identifier and calendar-like columns are deliberately preserved.
    """

    compacted_payload = dict(payload)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return compacted_payload

    compacted_rows: list[Any] = []
    changed = False
    for row in rows:
        if not isinstance(row, Mapping):
            compacted_rows.append(row)
            continue

        compacted_row: dict[str, Any] = {}
        for raw_column, value in row.items():
            column = str(raw_column)
            compacted_value = _compact_measure_value(column, value)
            if compacted_value != value:
                changed = True
            compacted_row[column] = compacted_value
        compacted_rows.append(compacted_row)

    compacted_payload["rows"] = compacted_rows
    if changed:
        compacted_payload["number_format"] = _NUMBER_FORMAT_NOTE
    return compacted_payload


def _compact_measure_value(column: str, value: Any) -> Any:
    if _is_identifier_or_period_column(column):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return value

    number = _as_finite_decimal(value)
    if number is None:
        return value

    magnitude = abs(number)
    for divisor, suffix in _NUMBER_SCALES:
        if magnitude >= divisor:
            scaled = number / divisor
            rendered = f"{scaled:.3f}".rstrip("0").rstrip(".")
            return f"{rendered}{suffix}"
    return value


def _is_identifier_or_period_column(column: str) -> bool:
    parts = set(re.findall(r"[A-Z0-9]+", column.upper()))
    return bool(parts & _IDENTIFIER_OR_PERIOD_PARTS)


def _as_finite_decimal(value: int | float | Decimal) -> Decimal | None:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None
