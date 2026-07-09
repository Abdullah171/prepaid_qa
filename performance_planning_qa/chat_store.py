"""PostgreSQL persistence for chat sessions and messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from performance_planning_qa.config import ChatStorageSettings
from performance_planning_qa.database import to_jsonable


DEFAULT_SESSION_TITLE = "New chat"


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
    def __init__(self, settings: ChatStorageSettings):
        self.settings = settings
        self._connection = None

    def connect(self):
        if self._connection is not None and not self._connection.closed:
            return self._connection

        self.settings.validate()
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise ChatStoreError(
                "Missing PostgreSQL dependency. Install project dependencies with `uv sync`."
            ) from exc

        self._connection = psycopg.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname=self.settings.database,
            user=self.settings.username,
            password=self.settings.password,
            sslmode=self.settings.sslmode,
            row_factory=dict_row,
        )
        self._connection.autocommit = True
        return self._connection

    def close(self) -> None:
        if self._connection is None:
            return
        self._connection.close()
        self._connection = None

    def ensure_schema(self) -> None:
        schema_sql = self.settings.schema_path.read_text(encoding="utf-8")
        with self.connect().cursor() as cursor:
            cursor.execute(schema_sql)

    def create_session(self, title: str | None = None) -> ChatSession:
        session_id = str(uuid4())
        cleaned_title = _normalize_title(title) or DEFAULT_SESSION_TITLE
        row = self._fetch_one(
            """
            INSERT INTO public.ppqa_chat_sessions (id, title)
            VALUES (%s, %s)
            RETURNING id::text, title, created_at, updated_at, 0::int AS message_count
            """,
            (session_id, cleaned_title),
        )
        return _session_from_row(row)

    def list_sessions(self) -> list[ChatSession]:
        rows = self._fetch_all(
            """
            SELECT
                s.id::text,
                s.title,
                s.created_at,
                s.updated_at,
                COUNT(m.id)::int AS message_count
            FROM public.ppqa_chat_sessions AS s
            LEFT JOIN public.ppqa_chat_messages AS m ON m.session_id = s.id
            GROUP BY s.id, s.title, s.created_at, s.updated_at
            ORDER BY s.updated_at DESC, s.created_at DESC
            """,
        )
        return [_session_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> ChatSession | None:
        row = self._fetch_optional(
            """
            SELECT
                s.id::text,
                s.title,
                s.created_at,
                s.updated_at,
                COUNT(m.id)::int AS message_count
            FROM public.ppqa_chat_sessions AS s
            LEFT JOIN public.ppqa_chat_messages AS m ON m.session_id = s.id
            WHERE s.id = %s
            GROUP BY s.id, s.title, s.created_at, s.updated_at
            """,
            (session_id,),
        )
        return _session_from_row(row) if row is not None else None

    def update_session_title(self, session_id: str, title: str) -> ChatSession | None:
        cleaned_title = _normalize_title(title)
        if not cleaned_title:
            return self.get_session(session_id)
        row = self._fetch_optional(
            """
            UPDATE public.ppqa_chat_sessions
            SET title = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id::text, title, created_at, updated_at, (
                SELECT COUNT(*)::int
                FROM public.ppqa_chat_messages
                WHERE session_id = public.ppqa_chat_sessions.id
            ) AS message_count
            """,
            (cleaned_title, session_id),
        )
        return _session_from_row(row) if row is not None else None

    def delete_session(self, session_id: str) -> bool:
        row = self._fetch_one(
            "DELETE FROM public.ppqa_chat_sessions WHERE id = %s RETURNING id::text",
            (session_id,),
        )
        return row is not None

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

        message_id = str(uuid4())
        payload = json.dumps(to_jsonable(metadata or {}), ensure_ascii=False)
        connection = self.connect()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.ppqa_chat_messages
                        (id, session_id, role, content, dry_run, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING
                        id::text,
                        session_id::text,
                        role,
                        content,
                        dry_run,
                        metadata,
                        created_at
                    """,
                    (message_id, session_id, role, content, dry_run, payload),
                )
                row = cursor.fetchone()
                cursor.execute(
                    "UPDATE public.ppqa_chat_sessions SET updated_at = NOW() WHERE id = %s",
                    (session_id,),
                )
        return _message_from_row(row)

    def list_messages(self, session_id: str, *, limit: int | None = None) -> list[ChatMessage]:
        params: tuple[Any, ...]
        if limit is None:
            query = """
                SELECT
                    id::text,
                    session_id::text,
                    role,
                    content,
                    dry_run,
                    metadata,
                    created_at
                FROM public.ppqa_chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """
            params = (session_id,)
        else:
            query = """
                SELECT *
                FROM (
                    SELECT
                        id::text,
                        session_id::text,
                        role,
                        content,
                        dry_run,
                        metadata,
                        created_at
                    FROM public.ppqa_chat_messages
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ) AS recent_messages
                ORDER BY created_at ASC
            """
            params = (session_id, limit)
        return [_message_from_row(row) for row in self._fetch_all(query, params)]

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        with self.connect().cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _fetch_optional(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect().cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect().cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


class ChatStoreError(RuntimeError):
    pass


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
    return cleaned[:120]


def _session_from_row(row: dict[str, Any]) -> ChatSession:
    return ChatSession(
        id=str(row["id"]),
        title=str(row["title"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        message_count=int(row.get("message_count") or 0),
    )


def _message_from_row(row: dict[str, Any]) -> ChatMessage:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return ChatMessage(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        dry_run=bool(row["dry_run"]),
        metadata=dict(metadata),
        created_at=row["created_at"],
    )
