"""Teradata execution using teradataml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging
import re
import time
from typing import Any

from performance_planning_qa.config import TeradataSettings


logger = logging.getLogger(__name__)

_CONNECTION_ERROR_MARKERS = (
    "[error 301]",
    "[error 398]",
    "lost connection to the teradata database",
    "failure sending start request message",
    "broken pipe",
    "connection reset",
    "connection aborted",
    "connection closed",
    "connection refused",
    "server closed the connection unexpectedly",
    "network communication failure",
    "network is unreachable",
    "no route to host",
    "socket is not connected",
    "unexpected eof",
    "use of closed network connection",
)

_CONNECTION_SQLSTATE_PATTERN = re.compile(r"sqlstate\W*08[a-z0-9]{3}")


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "row_count": self.row_count,
            "elapsed_ms": self.elapsed_ms,
            "rows": to_jsonable(self.rows),
        }


class TeradataClient:
    def __init__(self, settings: TeradataSettings):
        self.settings = settings
        self._connected = False
        self._execute_sql = None
        self._remove_context = None

    def connect(self) -> None:
        if self._connected:
            return
        self.settings.validate()
        try:
            from teradataml import create_context, execute_sql, remove_context
        except ImportError as exc:
            raise DatabaseConnectionError(
                "Missing Teradata dependency. Install it with "
                "`python -m pip install -r requirements.txt`."
            ) from exc

        kwargs: dict[str, Any] = {
            "host": self.settings.host,
            "username": self.settings.username,
            "password": self.settings.password,
        }
        optional = {
            "database": self.settings.database,
            "logmech": self.settings.logmech,
            "logdata": self.settings.logdata,
            "temp_database_name": self.settings.temp_database_name,
        }
        kwargs.update({key: value for key, value in optional.items() if value})

        try:
            create_context(**kwargs)
        except Exception as exc:
            raise DatabaseConnectionError(f"Failed to connect to Teradata: {exc}") from exc
        self._execute_sql = execute_sql
        self._remove_context = remove_context
        self._connected = True

    def close(self) -> None:
        self._disconnect(suppress_errors=False)

    def execute_select(self, sql: str) -> QueryResult:
        started = time.monotonic()
        for attempt in range(2):
            self.connect()
            if self._execute_sql is None:
                raise RuntimeError("Teradata execute_sql is not initialized.")

            try:
                cursor = self._execute_sql(sql)
                columns = _get_columns(cursor)
                raw_rows = _fetch_all_rows(cursor)
                break
            except Exception as exc:
                if not is_connection_error(exc):
                    raise DatabaseQueryError(f"Teradata query failed: {exc}") from exc

                # The SQL accepted by this client is read-only, so it is safe to
                # discard a dead teradataml context and execute it once more on a
                # fresh session. Always discard after the final failure as well so
                # a later request is not handed the same broken connection.
                self._disconnect(suppress_errors=True)
                if attempt == 0:
                    logger.warning(
                        "Teradata connection was lost; reconnecting and retrying "
                        "the read-only query once"
                    )
                    continue
                raise DatabaseConnectionError(
                    f"Lost connection to Teradata after reconnecting: {exc}"
                ) from exc

        rows = [_coerce_row(row, columns) for row in raw_rows]
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=elapsed_ms,
        )

    def __enter__(self) -> TeradataClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _disconnect(self, *, suppress_errors: bool) -> None:
        remove_context = self._remove_context
        self._connected = False
        self._execute_sql = None
        self._remove_context = None
        if remove_context is None:
            return
        try:
            remove_context()
        except Exception:
            if not suppress_errors:
                raise
            logger.warning(
                "Could not cleanly remove the failed Teradata context",
                exc_info=True,
            )


class DatabaseConnectionError(RuntimeError):
    pass


class DatabaseQueryError(RuntimeError):
    pass


def is_connection_error(exc: BaseException) -> bool:
    """Return whether an exception chain describes a lost database transport."""

    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))

        message = str(current).lower()
        sqlstate = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if str(sqlstate or "").upper().startswith("08"):
            return True
        if _CONNECTION_SQLSTATE_PATTERN.search(message):
            return True
        if any(marker in message for marker in _CONNECTION_ERROR_MARKERS):
            return True

        for linked in (current.__cause__, current.__context__):
            if isinstance(linked, BaseException):
                pending.append(linked)
        for arg in getattr(current, "args", ()):
            if isinstance(arg, BaseException):
                pending.append(arg)
    return False


def _get_columns(cursor: Any) -> list[str]:
    if hasattr(cursor, "keys"):
        keys = cursor.keys()
        return [str(key) for key in keys]
    description = getattr(cursor, "description", None)
    if description:
        return [str(item[0]) for item in description]
    return []


def _fetch_all_rows(cursor: Any) -> list[Any]:
    if hasattr(cursor, "fetchall"):
        return list(cursor.fetchall())
    if hasattr(cursor, "fetchmany"):
        rows = []
        while True:
            batch = list(cursor.fetchmany(10000))
            if not batch:
                return rows
            rows.extend(batch)
    rows = []
    for row in cursor:
        rows.append(row)
    return rows


def _coerce_row(row: Any, columns: list[str]) -> dict[str, Any]:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return {str(key): value for key, value in mapping.items()}
    if isinstance(row, dict):
        return {str(key): value for key, value in row.items()}
    return {column: value for column, value in zip(columns, row, strict=False)}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
