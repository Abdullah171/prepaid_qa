"""Displayed-table extraction, CSV intent, metadata, and serialization helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import html
import io
import json
import re
import unicodedata
from typing import Any, Literal, Mapping, Sequence


CSV_OFFER_TEXT = "Do you need this data in CSV format?"
CSV_READY_TEXT = "Your CSV file is ready to download below."

_CSV_REQUEST_RE = re.compile(
    r"(?:\bcsv\b|\bcomma[\s-]+separated(?:\s+values?)?\b)",
    re.IGNORECASE,
)
_CSV_FOLLOWUP_COMMAND_RE = re.compile(
    r"(?:please\s+)?(?:"
    r"csv(?:\s+(?:please|format|file))?"
    r"|(?:give|send)\s+me\s+(?:it|that|this|the\s+csv(?:\s+file)?|the\s+data)"
    r"(?:\s+(?:as|in)\s+csv(?:\s+format)?)?"
    r"|download\s+(?:it|that|this|the\s+csv(?:\s+file)?)"
    r"|export\s+(?:it|that|this|the\s+data)(?:\s+(?:as|in)\s+csv(?:\s+format)?)?"
    r"|(?:give|send|download|export)\s+(?:me\s+)?(?:the\s+)?csv(?:\s+file)?"
    r"|i\s+(?:need|want|would\s+like)\s+"
    r"(?:it|that|this|the\s+data|the\s+csv(?:\s+file)?)"
    r"(?:\s+(?:as|in)\s+csv(?:\s+format)?)?"
    r"|make\s+(?:it|that|this|the\s+data)\s+(?:a\s+)?csv(?:\s+file)?"
    r"|convert\s+(?:it|that|this|the\s+data)\s+to\s+csv(?:\s+format)?"
    r"|(?:can|could|would)\s+you\s+(?:please\s+)?"
    r"(?:give|send|provide|download|export)\s+(?:me\s+)?"
    r"(?:it|that|this|the\s+data|the\s+csv(?:\s+file)?)"
    r"(?:\s+(?:as|in)\s+csv(?:\s+format)?)?"
    r")",
    re.IGNORECASE,
)
_MARKDOWN_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass(frozen=True)
class DisplayedTable:
    """The exact compact table selected for display in the final answer."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class CSVExportSpec:
    """Persisted CSV artifact created from a displayed table or query result."""

    status: Literal["offered", "ready"]
    filename: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    source: Literal["displayed_answer_table", "query_result"] = (
        "displayed_answer_table"
    )
    source_row_count: int | None = None

    @property
    def row_count(self) -> int:
        if self.source_row_count is not None:
            return self.source_row_count
        return len(self.rows)

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": 2,
            "status": self.status,
            "filename": self.filename,
            "mime_type": "text/csv",
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "row_count": self.row_count,
            "source": self.source,
        }


def has_explicit_csv_request(question: str) -> bool:
    """Return whether the current question explicitly asks for CSV output."""

    return bool(_CSV_REQUEST_RE.search(str(question or "")))


def has_offered_csv(previous_result: dict[str, Any] | None) -> bool:
    """Return whether the immediately preceding result contains a usable offer."""

    if not isinstance(previous_result, dict):
        return False
    export = previous_result.get("csv_export")
    if not isinstance(export, dict) or export.get("status") != "offered":
        return False
    return displayed_table_from_payload(export) is not None


def is_csv_followup(
    question: str,
    previous_result: dict[str, Any] | None,
) -> bool:
    """Quickly recognize common acceptances before semantic classification."""

    if not has_offered_csv(previous_result):
        return False

    normalized = _normalize_followup(question)
    if not normalized:
        return False
    accepted = {
        "yes",
        "yes please",
        "yeah",
        "yeah please",
        "yep",
        "yep please",
        "sure",
        "sure please",
        "yeah sure",
        "absolutely",
        "please do",
        "go ahead",
        "that would be great",
        "i would like that",
        "نعم",
        "نعم من فضلك",
        "ايوه",
        "أيوه",
    }
    if normalized in accepted:
        return True
    if normalized.startswith(("yes ", "yeah ", "yep ", "sure ")):
        remaining = normalized.split()[1:]
        allowed_words = {
            "a",
            "an",
            "please",
            "sure",
            "do",
            "it",
            "this",
            "that",
            "data",
            "i",
            "need",
            "want",
            "would",
            "like",
            "download",
            "give",
            "send",
            "me",
            "to",
            "the",
            "csv",
            "file",
            "as",
            "in",
            "format",
            "also",
            "show",
            "graph",
            "chart",
            "plot",
            "visualization",
            "of",
            "for",
        }
        if len(remaining) <= 20 and set(remaining) <= allowed_words:
            return True
    return bool(_CSV_FOLLOWUP_COMMAND_RE.fullmatch(normalized))


def extract_displayed_table(answer: str | None) -> DisplayedTable | None:
    """Extract the first GitHub-flavored Markdown table shown in an answer."""

    lines = str(answer or "").splitlines()
    for index in range(len(lines) - 2):
        columns = _split_markdown_row(lines[index])
        separators = _split_markdown_row(lines[index + 1])
        if (
            not columns
            or not separators
            or len(columns) != len(separators)
            or not all(
                _MARKDOWN_SEPARATOR_RE.fullmatch(cell.strip())
                for cell in separators
            )
        ):
            continue

        rows: list[tuple[str, ...]] = []
        for line in lines[index + 2 :]:
            cells = _split_markdown_row(line)
            if cells is None or len(cells) != len(columns):
                break
            rows.append(tuple(_plain_markdown_cell(cell) for cell in cells))
        if rows:
            return DisplayedTable(
                columns=tuple(_plain_markdown_cell(column) for column in columns),
                rows=tuple(rows),
            )
    return None


def strip_embedded_csv_dump(answer: str | None) -> str:
    """Remove a model-printed raw CSV section after an already displayed table."""

    lines = str(answer or "").splitlines()
    for index, line in enumerate(lines):
        label = _plain_markdown_cell(line).strip().rstrip(":").casefold()
        if label not in {"csv", "csv data", "csv download", "csv output"}:
            continue
        preceding_answer = "\n".join(lines[:index]).rstrip()
        if extract_displayed_table(preceding_answer) is not None:
            return preceding_answer
    return str(answer or "").strip()


def build_csv_export_spec(
    question: str,
    *,
    table: DisplayedTable | None,
) -> CSVExportSpec | None:
    """Build an offer/download only when a table was actually shown."""

    if table is None or not table.columns or not table.rows:
        return None
    status: Literal["offered", "ready"] = (
        "ready" if has_explicit_csv_request(question) else "offered"
    )
    return CSVExportSpec(
        status=status,
        filename=build_csv_filename(question),
        columns=table.columns,
        rows=table.rows,
    )


def build_query_result_csv_export_spec(
    question: str,
    *,
    columns: Sequence[str],
    row_count: int,
) -> CSVExportSpec | None:
    """Build a CSV reference that reuses rows already stored in query_result."""

    normalized_columns = tuple(str(column) for column in columns)
    if not normalized_columns or row_count <= 0:
        return None
    return CSVExportSpec(
        status="ready",
        filename=build_csv_filename(question),
        columns=normalized_columns,
        rows=(),
        source="query_result",
        source_row_count=row_count,
    )


def build_ready_csv_export_spec(previous_export: dict[str, Any]) -> CSVExportSpec | None:
    """Promote an earlier offer while retaining its exact displayed table."""

    table = displayed_table_from_payload(previous_export)
    if table is None:
        return None
    raw_filename = str(previous_export.get("filename") or "").strip()
    filename = (
        raw_filename
        if raw_filename.lower().endswith(".csv")
        else "prepaid-qa-data.csv"
    )
    return CSVExportSpec(
        status="ready",
        filename=filename,
        columns=table.columns,
        rows=table.rows,
        source=(
            "query_result"
            if previous_export.get("source") == "query_result"
            else "displayed_answer_table"
        ),
    )


def displayed_table_from_payload(value: Any) -> DisplayedTable | None:
    """Validate and rehydrate a displayed table stored in message metadata."""

    if not isinstance(value, dict):
        return None
    raw_columns = value.get("columns")
    raw_rows = value.get("rows")
    if not isinstance(raw_columns, list) or not raw_columns:
        return None
    if not isinstance(raw_rows, list) or not raw_rows:
        return None
    columns = tuple(str(column) for column in raw_columns)
    rows: list[tuple[str, ...]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != len(columns):
            return None
        rows.append(tuple("" if value is None else str(value) for value in raw_row))
    return DisplayedTable(columns=columns, rows=tuple(rows))


def append_csv_message(answer: str | None, export: CSVExportSpec | None) -> str:
    """Append the application-owned offer/readiness message to an LLM answer."""

    cleaned_answer = str(answer or "").strip()
    if export is None:
        return cleaned_answer
    suffix = CSV_READY_TEXT if export.status == "ready" else CSV_OFFER_TEXT
    if suffix.casefold() in cleaned_answer.casefold():
        return cleaned_answer
    return f"{cleaned_answer}\n\n{suffix}".strip()


def csv_export_to_bytes(
    export: dict[str, Any],
    *,
    query_result: dict[str, Any] | None = None,
) -> bytes:
    """Serialize a stored export artifact as an Excel-friendly UTF-8 CSV."""

    table = (
        _query_result_table(query_result, export=export)
        if export.get("source") == "query_result"
        else displayed_table_from_payload(export)
    )
    if table is None:
        raise ValueError("csv_export does not contain a valid table")

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(table.columns)
    writer.writerows(table.rows)

    # The BOM keeps Arabic and other non-ASCII labels readable in Excel while
    # remaining valid UTF-8 for standards-compliant CSV readers.
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _query_result_table(
    query_result: dict[str, Any] | None,
    *,
    export: dict[str, Any],
) -> DisplayedTable | None:
    if not isinstance(query_result, dict):
        return None
    raw_columns = export.get("columns") or query_result.get("columns")
    raw_rows = query_result.get("rows")
    if not isinstance(raw_columns, list) or not raw_columns:
        return None
    if not isinstance(raw_rows, list) or not raw_rows:
        return None
    columns = tuple(str(column) for column in raw_columns)
    rows: list[tuple[str, ...]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            return None
        rows.append(tuple(_query_result_cell(raw_row.get(column)) for column in columns))
    return DisplayedTable(columns=columns, rows=tuple(rows))


def build_csv_filename(question: str) -> str:
    """Create a portable, bounded filename from the analytical request."""

    ascii_question = unicodedata.normalize("NFKD", str(question or "")).encode(
        "ascii", "ignore"
    ).decode("ascii")
    words = re.findall(r"[a-z0-9]+", ascii_question.casefold())
    ignored = {"csv", "format", "file", "download", "export", "please"}
    useful_words = [word for word in words if word not in ignored][:8]
    slug = "-".join(useful_words)[:64].strip("-")
    if not slug:
        slug = "prepaid-qa-data"
    return f"{slug}.csv"


def _query_result_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return str(isoformat())
        except (TypeError, ValueError):
            pass
    return str(value)


def _split_markdown_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return None

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            if char == "|":
                current.append("|")
            else:
                current.extend(("\\", char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())

    if stripped.startswith("|") and cells and cells[0] == "":
        cells = cells[1:]
    if stripped.endswith("|") and cells and cells[-1] == "":
        cells = cells[:-1]
    return cells or None


def _plain_markdown_cell(value: str) -> str:
    text = _MARKDOWN_BREAK_RE.sub("\n", value.strip())
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = text.replace("`", "")
    text = re.sub(r"\\([\\|`*_{}\[\]()#+.!-])", r"\1", text)
    return html.unescape(text).strip()


def _normalize_followup(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value or "").casefold()).split())
