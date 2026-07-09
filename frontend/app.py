"""Streamlit frontend for the Performance Planning Q&A backend."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from styles import APP_CSS


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    st.set_page_config(
        page_title="Performance Planning Q&A",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(APP_CSS, unsafe_allow_html=True)
    _init_state()

    client = _sidebar()
    active_session_id = st.session_state.get("active_session_id")

    session_detail = None
    if active_session_id:
        try:
            session_detail = client.get_session(active_session_id)
        except ApiError as exc:
            st.session_state.active_session_id = None
            st.error(str(exc))

    _render_header(session_detail)

    if session_detail:
        _render_messages(session_detail.get("messages", []))
    else:
        _render_empty_state()

    prompt = st.chat_input("Ask a performance planning question")
    if prompt:
        _submit_prompt(client, prompt)


def _init_state() -> None:
    st.session_state.setdefault(
        "api_base_url",
        os.getenv("PPQA_API_BASE_URL", DEFAULT_API_BASE_URL),
    )
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("dry_run", False)


def _sidebar() -> ApiClient:
    with st.sidebar:
        st.title("Performance Planning")
        api_base_url = st.text_input("API URL", key="api_base_url")
        st.toggle("Dry run", key="dry_run", help="Generate SQL without executing it.")
        client = ApiClient(api_base_url)

        try:
            client.health()
            st.markdown('<div class="ppqa-health-ok">API connected</div>', unsafe_allow_html=True)
        except ApiError as exc:
            st.markdown('<div class="ppqa-health-bad">API unavailable</div>', unsafe_allow_html=True)
            st.caption(str(exc))

        st.divider()

        if st.button("New chat", use_container_width=True, type="primary"):
            try:
                session = client.create_session()
                st.session_state.active_session_id = session["id"]
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))

        st.caption("Sessions")
        try:
            sessions = client.list_sessions()
        except ApiError as exc:
            st.error(str(exc))
            sessions = []

        if not st.session_state.active_session_id and sessions:
            st.session_state.active_session_id = sessions[0]["id"]

        for session in sessions:
            _render_session_row(client, session)

    return client


def _render_session_row(client: ApiClient, session: dict[str, Any]) -> None:
    session_id = session["id"]
    is_active = st.session_state.active_session_id == session_id
    title = session.get("title") or "New chat"
    label = title if len(title) <= 38 else f"{title[:35].rstrip()}..."
    if is_active:
        label = f"> {label}"

    cols = st.sidebar.columns([0.78, 0.22], gap="small")
    if cols[0].button(label, key=f"select-{session_id}", use_container_width=True):
        st.session_state.active_session_id = session_id
        st.rerun()
    if cols[1].button("x", key=f"delete-{session_id}", help="Delete session"):
        try:
            client.delete_session(session_id)
            if is_active:
                st.session_state.active_session_id = None
            st.rerun()
        except ApiError as exc:
            st.sidebar.error(str(exc))
    st.sidebar.markdown(
        f'<div class="ppqa-session-meta">{session.get("message_count", 0)} messages</div>',
        unsafe_allow_html=True,
    )


def _render_header(session_detail: dict[str, Any] | None) -> None:
    if session_detail:
        session = session_detail["session"]
        title = session.get("title") or "New chat"
        count = session.get("message_count", 0)
    else:
        title = "Performance Planning Q&A"
        count = 0
    st.markdown(
        f"""
        <div class="ppqa-header">
          <div class="ppqa-title">{_html_escape(title)}</div>
          <div class="ppqa-subtitle">{count} saved messages</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state() -> None:
    st.markdown(
        """
        <div class="ppqa-empty">
          <div class="ppqa-empty-inner">
            <div class="ppqa-empty-title">Start a planning analysis</div>
            <div class="ppqa-empty-copy">
              Ask about postpaid base, sales, churn, or monthly revenue.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_messages(messages: list[dict[str, Any]]) -> None:
    if not messages:
        _render_empty_state()
        return

    for message in messages:
        role = message.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(message.get("content") or "")
            if role == "assistant":
                _render_assistant_artifacts(message.get("metadata") or {})


def _render_assistant_artifacts(metadata: dict[str, Any]) -> None:
    sql = metadata.get("sql")
    error = metadata.get("error")
    query_result = metadata.get("query_result")

    if error:
        st.error(error)
    if sql:
        with st.expander("SQL", expanded=False):
            st.code(sql, language="sql")

    if not query_result:
        return

    columns = query_result.get("columns") or []
    row_count = query_result.get("row_count", 0)
    elapsed_ms = query_result.get("elapsed_ms", 0)
    rows = query_result.get("rows") or []

    metric_cols = st.columns(3)
    metric_cols[0].metric("Rows", row_count)
    metric_cols[1].metric("Columns", len(columns))
    metric_cols[2].metric("Query time", f"{elapsed_ms} ms")

    if rows:
        with st.expander("Result rows", expanded=False):
            st.dataframe(rows, use_container_width=True, hide_index=True)


def _submit_prompt(client: ApiClient, prompt: str) -> None:
    session_id = st.session_state.active_session_id
    if not session_id:
        try:
            session = client.create_session()
            session_id = session["id"]
            st.session_state.active_session_id = session_id
        except ApiError as exc:
            st.error(str(exc))
            return

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Running analysis"):
            try:
                response = client.ask_session(
                    session_id,
                    prompt,
                    dry_run=bool(st.session_state.get("dry_run", False)),
                )
            except ApiError as exc:
                st.error(str(exc))
                return

        assistant_message = response["assistant_message"]
        st.markdown(assistant_message.get("content") or "")
        _render_assistant_artifacts(assistant_message.get("metadata") or {})

    st.rerun()


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


if __name__ == "__main__":
    main()
