"""PostgreSQL, DuckDB, and Teradata persistence for chat sessions and messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Any
from uuid import uuid4

from performance_planning_qa.config import ChatStorageSettings, TeradataSettings
from performance_planning_qa.database import is_connection_error, to_jsonable


DEFAULT_SESSION_TITLE = "New chat"
MAX_SESSION_TITLE_LENGTH = 500


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatSession:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
        }


@dataclass(frozen=True)
class ChatMessage:
    id: str
    session_id: str
    role: str
    content: str
    dry_run: bool
    metadata: dict[str, Any]
    created_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "dry_run": self.dry_run,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class ChatStore:
    """Persist chat history in PostgreSQL, DuckDB, or Teradata."""

    def __init__(
        self,
        settings: ChatStorageSettings,
        teradata_settings: TeradataSettings | None = None,
    ):
        self.settings = settings
        self.teradata_settings = teradata_settings
        self._connection = None

    @property
    def is_teradata(self) -> bool:
        return self.settings.backend == "teradata"

    @property
    def is_duckdb(self) -> bool:
        return self.settings.backend == "duckdb"

    @property
    def sessions_table(self) -> str:
        if self.is_teradata:
            return f"{self.settings.teradata_database}.SC_PPQA_CHAT_SESSIONS"
        if self.is_duckdb:
            return "SC_PPQA_CHAT_SESSIONS"
        return "public.SC_PPQA_CHAT_SESSIONS"

    @property
    def messages_table(self) -> str:
        if self.is_teradata:
            return f"{self.settings.teradata_database}.SC_PPQA_CHAT_MESSAGES"
        if self.is_duckdb:
            return "SC_PPQA_CHAT_MESSAGES"
        return "public.SC_PPQA_CHAT_MESSAGES"

    @property
    def session_title_column(self) -> str:
        return "TITLE_" if self.is_teradata else "title"

    @property
    def placeholder(self) -> str:
        return "?" if self.is_teradata or self.is_duckdb else "%s"

    @property
    def current_timestamp(self) -> str:
        return "CURRENT_TIMESTAMP" if self.is_duckdb else "CURRENT_TIMESTAMP(6)"

    def connect(self):
        if self._connection is not None:
            return self._connection

        self.settings.validate()
        if self.is_teradata:
            self._connection = self._connect_teradata()
        elif self.is_duckdb:
            self._connection = self._connect_duckdb()
        else:
            self._connection = self._connect_postgres()
        return self._connection

    def _connect_duckdb(self):
        try:
            import duckdb
        except ImportError as exc:
            raise ChatStoreError(
                "Missing DuckDB dependency. Install it with "
                "`python -m pip install -r requirements.txt`."
            ) from exc

        database_path = self.settings.duckdb_path
        try:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            return duckdb.connect(str(database_path))
        except Exception as exc:
            raise ChatStoreError(
                f"Failed to open DuckDB chat storage at {database_path}: {exc}"
            ) from exc

    def _connect_postgres(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise ChatStoreError(
                "Missing PostgreSQL dependency. Install it with "
                "`python -m pip install -r requirements.txt`."
            ) from exc

        connection = psycopg.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname=self.settings.database,
            user=self.settings.username,
            password=self.settings.password,
            sslmode=self.settings.sslmode,
            row_factory=dict_row,
        )
        connection.autocommit = True
        return connection

    def _connect_teradata(self):
        if self.teradata_settings is None:
            raise ChatStoreError("Teradata settings are required when chat_db=teradata")
        self.teradata_settings.validate()
        try:
            import teradatasql
        except ImportError as exc:
            raise ChatStoreError(
                "Missing Teradata dependency. Install it with "
                "`python -m pip install -r requirements.txt`."
            ) from exc

        kwargs: dict[str, Any] = {
            "host": self.teradata_settings.host,
            "user": self.teradata_settings.username,
            "password": self.teradata_settings.password,
            "database": self.settings.teradata_database,
        }
        if self.teradata_settings.logmech:
            kwargs["logmech"] = self.teradata_settings.logmech
        if self.teradata_settings.logdata:
            kwargs["logdata"] = self.teradata_settings.logdata
        try:
            return teradatasql.connect(**kwargs)
        except Exception as exc:
            raise ChatStoreError(f"Failed to connect chat storage to Teradata: {exc}") from exc

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        connection.close()

    def ensure_schema(self) -> None:
        if self.is_teradata:
            try:
                self._fetch_all(f"SELECT TOP 1 id FROM {self.sessions_table}")
                self._fetch_all(f"SELECT TOP 1 id FROM {self.messages_table}")
            except Exception as exc:
                raise ChatStoreError(
                    "Teradata chat tables are unavailable. Run sql/chat_memory_schema.sql "
                    f"in {self.settings.teradata_database}."
                ) from exc
            return

        if self.is_duckdb:
            schema_sql = self.settings.duckdb_schema_path.read_text(encoding="utf-8")
            self.connect().execute(schema_sql)
            return

        schema_sql = self.settings.local_schema_path.read_text(encoding="utf-8")
        with self.connect().cursor() as cursor:
            cursor.execute(schema_sql)

    def create_session(self, title: str | None = None) -> ChatSession:
        session_id = str(uuid4())
        cleaned_title = _normalize_title(title) or DEFAULT_SESSION_TITLE
        p = self.placeholder
        self._execute_write(
            f"""
            INSERT INTO {self.sessions_table} (id, {self.session_title_column})
            VALUES ({p}, {p})
            """,
            (session_id, cleaned_title),
        )
        session = self.get_session(session_id)
        if session is None:
            raise ChatStoreError("The new chat session could not be read after insertion")
        return session

    def list_sessions(self) -> list[ChatSession]:
        rows = self._fetch_all(
            f"""
            SELECT
                s.id,
                s.{self.session_title_column},
                s.created_at,
                s.updated_at,
                CAST(COUNT(m.id) AS INTEGER) AS message_count
            FROM {self.sessions_table} AS s
            LEFT JOIN {self.messages_table} AS m ON m.session_id = s.id
            GROUP BY s.id, s.{self.session_title_column}, s.created_at, s.updated_at
            ORDER BY s.updated_at DESC, s.created_at DESC
            """
        )
        return [_session_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> ChatSession | None:
        p = self.placeholder
        row = self._fetch_optional(
            f"""
            SELECT
                s.id,
                s.{self.session_title_column},
                s.created_at,
                s.updated_at,
                CAST(COUNT(m.id) AS INTEGER) AS message_count
            FROM {self.sessions_table} AS s
            LEFT JOIN {self.messages_table} AS m ON m.session_id = s.id
            WHERE s.id = {p}
            GROUP BY s.id, s.{self.session_title_column}, s.created_at, s.updated_at
            """,
            (session_id,),
        )
        return _session_from_row(row) if row is not None else None

    def update_session_title(self, session_id: str, title: str) -> ChatSession | None:
        cleaned_title = _normalize_title(title)
        if not cleaned_title:
            return self.get_session(session_id)
        p = self.placeholder
        self._execute_write(
            f"""
            UPDATE {self.sessions_table}
            SET {self.session_title_column} = {p}, updated_at = {self.current_timestamp}
            WHERE id = {p}
            """,
            (cleaned_title, session_id),
        )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        if self.get_session(session_id) is None:
            return False
        p = self.placeholder
        self._execute_writes(
            (
                (f"DELETE FROM {self.messages_table} WHERE session_id = {p}", (session_id,)),
                (f"DELETE FROM {self.sessions_table} WHERE id = {p}", (session_id,)),
            )
        )
        return True

    def add_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        dry_run: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported chat message role: {role!r}")
        if self.get_session(session_id) is None:
            raise ChatStoreError(f"Chat session does not exist: {session_id}")

        message_id = str(uuid4())
        payload = json.dumps(
            to_jsonable(metadata or {}),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        p = self.placeholder
        metadata_value = p if self.is_teradata or self.is_duckdb else f"{p}::jsonb"
        self._execute_writes(
            (
                (
                    f"""
                    INSERT INTO {self.messages_table}
                        (id, session_id, message_role, content, dry_run, metadata)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {metadata_value})
                    """,
                    (
                        message_id,
                        session_id,
                        role,
                        content,
                        int(dry_run) if self.is_teradata else dry_run,
                        payload,
                    ),
                ),
                (
                    f"""
                    UPDATE {self.sessions_table}
                    SET updated_at = {self.current_timestamp}
                    WHERE id = {p}
                    """,
                    (session_id,),
                ),
            )
        )
        row = self._fetch_optional(
            f"""
            SELECT id, session_id, message_role, content, dry_run, metadata, created_at
            FROM {self.messages_table}
            WHERE id = {p}
            """,
            (message_id,),
        )
        if row is None:
            raise ChatStoreError("The new chat message could not be read after insertion")
        return _message_from_row(row)

    def list_messages(self, session_id: str, *, limit: int | None = None) -> list[ChatMessage]:
        p = self.placeholder
        rows = self._fetch_all(
            f"""
            SELECT id, session_id, message_role, content, dry_run, metadata, created_at
            FROM {self.messages_table}
            WHERE session_id = {p}
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be zero or greater")
            rows = rows[-limit:] if limit else []
        return [_message_from_row(row) for row in rows]

    def _execute_write(self, query: str, params: tuple[Any, ...] = ()) -> None:
        self._execute_writes(((query, params),))

    def _execute_writes(
        self,
        statements: tuple[tuple[str, tuple[Any, ...]], ...],
    ) -> None:
        # Probe the cached session before beginning a write. If it went stale
        # while the app was idle, reconnect before any transaction starts.
        # A write that itself loses the network is never replayed because its
        # commit outcome may be unknown.
        connection = self._writable_connection()
        if self.is_duckdb:
            try:
                connection.execute("BEGIN TRANSACTION")
                for query, params in statements:
                    connection.execute(query, params)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return

        if not self.is_teradata:
            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        for query, params in statements:
                            cursor.execute(query, params)
            except Exception as exc:
                if is_connection_error(exc):
                    self._discard_connection()
                raise
            return

        try:
            with connection.cursor() as cursor:
                for query, params in statements:
                    cursor.execute(query, params)
            connection.commit()
        except Exception as exc:
            rollback_error: Exception | None = None
            try:
                connection.rollback()
            except Exception as rollback_exc:
                rollback_error = rollback_exc
                logger.warning(
                    "Could not roll back the failed Teradata chat transaction",
                    exc_info=True,
                )
            if is_connection_error(exc) or (
                rollback_error is not None and is_connection_error(rollback_error)
            ):
                self._discard_connection()
            raise

    def _fetch_optional(
        self,
        query: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        for attempt in range(2):
            try:
                with self.connect().cursor() as cursor:
                    cursor.execute(query, params)
                    columns = [str(item[0]).lower() for item in (cursor.description or ())]
                    raw_rows = cursor.fetchall()
                break
            except Exception as exc:
                if not is_connection_error(exc):
                    raise
                self._discard_connection()
                if attempt == 0:
                    logger.warning(
                        "Chat database connection was lost; reconnecting and "
                        "retrying the read once"
                    )
                    continue
                raise
        rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            if isinstance(raw_row, dict):
                row = {str(key).lower(): value for key, value in raw_row.items()}
            else:
                row = dict(zip(columns, raw_row, strict=False))
            rows.append({key: _read_lob(value) for key, value in row.items()})
        return rows

    def _writable_connection(self):
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            if not is_connection_error(exc):
                raise
            self._discard_connection()
            logger.warning(
                "Chat database connection failed its pre-write probe; reconnecting"
            )
            connection = self.connect()
        return connection

    def _discard_connection(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        try:
            connection.close()
        except Exception:
            logger.warning(
                "Could not cleanly close the failed chat database connection",
                exc_info=True,
            )


class ChatStoreError(RuntimeError):
    pass


def _read_lob(value: Any) -> Any:
    """Convert a Teradata CLOB value to text while leaving scalar values unchanged."""

    reader = getattr(value, "read", None)
    return reader() if callable(reader) else value


def make_session_title(question: str) -> str:
    title = " ".join(question.strip().split())
    if len(title) <= 64:
        return title or DEFAULT_SESSION_TITLE
    return f"{title[:61].rstrip()}..."


def _normalize_title(title: str | None) -> str | None:
    if title is None:
        return None
    cleaned = " ".join(title.strip().split())
    if not cleaned:
        return None
    return cleaned[:MAX_SESSION_TITLE_LENGTH]


def _session_from_row(row: dict[str, Any]) -> ChatSession:
    return ChatSession(
        id=str(row["id"]),
        title=str(row.get("title_") if "title_" in row else row["title"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        message_count=int(row.get("message_count") or 0),
    )


def _message_from_row(row: dict[str, Any]) -> ChatMessage:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    metadata = _without_legacy_query_result_csv_rows(metadata)
    return ChatMessage(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        role=str(row["message_role"]),
        content=str(row["content"]),
        dry_run=bool(row["dry_run"]),
        metadata=dict(metadata),
        created_at=row["created_at"],
    )


def _without_legacy_query_result_csv_rows(metadata: Any) -> dict[str, Any]:
    """Drop CSV rows duplicated by older context-limit fallback messages."""

    if not isinstance(metadata, dict):
        return {}
    export = metadata.get("csv_export")
    query_result = metadata.get("query_result")
    if (
        not isinstance(export, dict)
        or export.get("source") != "query_result"
        or not export.get("rows")
        or not isinstance(query_result, dict)
        or not query_result.get("rows")
    ):
        return metadata
    compacted = dict(metadata)
    compacted_export = dict(export)
    compacted_export["rows"] = []
    compacted["csv_export"] = compacted_export
    return compacted
