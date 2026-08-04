"""Streamlit frontend for the Performance Planning Q&A backend."""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

# PyArrow 25 defaults to mimalloc. On this macOS/Python build its per-thread
# heap initialization can segfault while Streamlit serializes Vega chart data.
# Select Arrow's system allocator before Streamlit/PyArrow are loaded.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import streamlit as st

try:
    import pyarrow as pa

    if pa.default_memory_pool().backend_name != "system":
        pa.set_memory_pool(pa.system_memory_pool())
except Exception:
    # Streamlit owns PyArrow; if its import contract changes, keep the app
    # usable and let ordinary chart error handling report the problem.
    logging.getLogger(__name__).warning(
        "Could not select PyArrow's system memory pool",
        exc_info=True,
    )

# Support both documented project-root launches and `streamlit run app.py`
# from inside the frontend directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis_runner import AnalysisRunner
from api_client import ApiClient, ApiError
from performance_planning_qa.cancellation import AnalysisCancelled
from performance_planning_qa.csv_export import csv_export_to_bytes
from user_messages import (
    ANALYSIS_UNAVAILABLE_MESSAGE,
    SERVICE_UNAVAILABLE_MESSAGE,
)
from styles import APP_CSS
from streamlit_logging import install_stale_fragment_info_filter


logger = logging.getLogger(__name__)
install_stale_fragment_info_filter()

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
MAX_RENDERED_RESULT_ROWS = 200
INITIAL_RENDERED_MESSAGES = 24
MESSAGE_RENDER_BATCH = 20
INITIAL_SIDEBAR_SESSIONS = 30
SIDEBAR_SESSION_BATCH = 30
FAILED_CONNECTION_RETRY_SECONDS = 15.0
MAX_QUESTION_CHARS = 4_000
ALLOW_API_URL_EDIT = os.getenv("PPQA_ALLOW_API_URL_EDIT", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STC_CHART_COLORS = (
    "#4F008C",
    "#00C2C7",
    "#FF375E",
    "#FFB71B",
    "#1D252D",
    "#8F5DA2",
)
_ISO_TEMPORAL_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


@st.cache_resource(
    scope="session",
    max_entries=4,
    show_spinner=False,
    on_release=lambda client: client.close(),
)
def _get_api_client(base_url: str) -> ApiClient:
    """Reuse HTTP connections without sharing mutable clients across users."""

    return ApiClient(base_url)


@st.cache_resource(
    scope="session",
    show_spinner=False,
    on_release=lambda runner: runner.close(),
)
def _get_analysis_runner() -> AnalysisRunner:
    return AnalysisRunner()


def main() -> None:
    st.set_page_config(
        page_title="Performance Planning Q&A",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(APP_CSS, unsafe_allow_html=True)
    _init_state()

    try:
        client = _get_api_client(st.session_state.api_base_url)
    except ApiError as exc:
        _log_frontend_error("Could not create the API client", exc)
        st.warning(SERVICE_UNAVAILABLE_MESSAGE)
        return

    runner = _get_analysis_runner()
    active_job = runner.active_job()
    _sidebar(client, analysis_running=active_job is not None)
    requested_session_id = st.session_state.get("active_session_id")
    session_detail = _load_active_session(client)
    if (
        requested_session_id
        and session_detail is None
        and st.session_state.get("connection_error")
    ):
        st.warning(SERVICE_UNAVAILABLE_MESSAGE)

    _render_header(session_detail, analysis_running=active_job is not None)

    if session_detail and session_detail.get("messages"):
        _render_messages(
            session_detail.get("messages", []),
            session_id=session_detail["session"]["id"],
        )
    elif active_job is None and st.session_state.get("failed_analysis") is None:
        _render_empty_state()

    _render_failed_analysis()
    analysis_notice = st.session_state.pop("analysis_notice", None)
    if analysis_notice:
        st.toast(str(analysis_notice), icon=":material/stop_circle:")
    if active_job is None:
        _render_question_composer()
    else:
        _render_active_analysis()


def _init_state() -> None:
    st.session_state.setdefault(
        "api_base_url",
        os.getenv("PPQA_API_BASE_URL", DEFAULT_API_BASE_URL),
    )
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("dry_run", False)
    st.session_state.setdefault("enable_thinking", True)
    st.session_state.setdefault("show_source", False)
    st.session_state.setdefault("sessions_cache", None)
    st.session_state.setdefault("sessions_loaded_at", 0.0)
    st.session_state.setdefault("connection_error", None)
    st.session_state.setdefault("session_details", {})
    st.session_state.setdefault("sidebar_session_limit", INITIAL_SIDEBAR_SESSIONS)
    st.session_state.setdefault("message_render_limits", {})
    st.session_state.setdefault("failed_analysis", None)
    st.session_state.setdefault("sidebar_action_error", None)


def _reset_frontend_cache() -> None:
    st.session_state.sessions_cache = None
    st.session_state.sessions_loaded_at = 0.0
    st.session_state.connection_error = None
    st.session_state.session_details = {}
    st.session_state.active_session_id = None
    st.session_state.sidebar_session_limit = INITIAL_SIDEBAR_SESSIONS
    st.session_state.message_render_limits = {}
    st.session_state.failed_analysis = None
    st.session_state.sidebar_action_error = None


def _load_sessions(
    client: ApiClient,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    cached = st.session_state.get("sessions_cache")
    last_attempt = float(st.session_state.get("sessions_loaded_at", 0.0))
    retry_due = time.monotonic() - last_attempt >= FAILED_CONNECTION_RETRY_SECONDS
    should_load = force or cached is None
    if st.session_state.get("connection_error") and retry_due:
        should_load = True
    if not should_load:
        return cached or []

    st.session_state.sessions_loaded_at = time.monotonic()
    try:
        sessions = client.list_sessions()
        if not isinstance(sessions, list) or not all(
            isinstance(session, dict) and session.get("id")
            for session in sessions
        ):
            raise ApiError("API returned an invalid chat history")
    except ApiError as exc:
        _log_frontend_error("Could not load chat sessions", exc)
        st.session_state.connection_error = SERVICE_UNAVAILABLE_MESSAGE
        if cached is None:
            st.session_state.sessions_cache = []
        return cached or []

    st.session_state.sessions_cache = sessions
    st.session_state.connection_error = None
    return sessions


def _load_active_session(client: ApiClient) -> dict[str, Any] | None:
    session_id = st.session_state.get("active_session_id")
    if not session_id:
        return None

    details = st.session_state.get("session_details", {})
    cached = details.get(session_id)
    if cached is not None:
        return cached

    try:
        detail = client.get_session(session_id)
        if (
            not isinstance(detail, dict)
            or not isinstance(detail.get("session"), dict)
            or not isinstance(detail.get("messages"), list)
        ):
            raise ApiError("API returned an invalid chat session")
    except ApiError as exc:
        _log_frontend_error("Could not load the active chat session", exc)
        st.session_state.connection_error = SERVICE_UNAVAILABLE_MESSAGE
        st.session_state.active_session_id = None
        return None

    details = dict(details)
    details[session_id] = detail
    st.session_state.session_details = details
    st.session_state.connection_error = None
    return detail


def _refresh_sessions(client: ApiClient) -> None:
    st.session_state.sidebar_action_error = None
    _load_sessions(client, force=True)
    if st.session_state.get("connection_error") is None:
        st.session_state.session_details = {}


def _start_new_chat() -> None:
    st.session_state.active_session_id = None
    st.session_state.failed_analysis = None
    st.session_state.sidebar_action_error = None


def _select_session(session_id: str) -> None:
    st.session_state.active_session_id = session_id
    st.session_state.failed_analysis = None
    st.session_state.sidebar_action_error = None


def _delete_session(client: ApiClient, session_id: str) -> None:
    try:
        client.delete_session(session_id)
    except ApiError as exc:
        _log_frontend_error("Could not delete a chat session", exc)
        st.session_state.sidebar_action_error = SERVICE_UNAVAILABLE_MESSAGE
        return

    sessions = st.session_state.get("sessions_cache") or []
    st.session_state.sessions_cache = [
        session for session in sessions if session.get("id") != session_id
    ]
    details = dict(st.session_state.get("session_details", {}))
    details.pop(session_id, None)
    st.session_state.session_details = details
    if st.session_state.get("active_session_id") == session_id:
        st.session_state.active_session_id = None
    st.session_state.failed_analysis = None
    st.session_state.sidebar_action_error = None


def _show_more_sessions() -> None:
    st.session_state.sidebar_session_limit = (
        int(st.session_state.sidebar_session_limit) + SIDEBAR_SESSION_BATCH
    )


def _show_more_messages(session_id: str) -> None:
    limits = dict(st.session_state.get("message_render_limits", {}))
    limits[session_id] = int(
        limits.get(session_id, INITIAL_RENDERED_MESSAGES)
    ) + MESSAGE_RENDER_BATCH
    st.session_state.message_render_limits = limits


def _sidebar(client: ApiClient, *, analysis_running: bool) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="ppqa-brand">
              <div class="ppqa-brand-mark">stc</div>
              <div>
                <div class="ppqa-brand-title">Performance Planning</div>
                <div class="ppqa-brand-subtitle">Analytics Q&A</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if ALLOW_API_URL_EDIT:
            st.text_input(
                "API URL",
                key="api_base_url",
                disabled=analysis_running,
                on_change=_reset_frontend_cache,
                help="Development override. Configure PPQA_API_BASE_URL in production.",
            )
        st.toggle(
            "Dry run",
            key="dry_run",
            disabled=analysis_running,
            help="Generate SQL without executing it.",
        )
        st.toggle(
            "Thinking",
            key="enable_thinking",
            disabled=analysis_running,
            help="Allow the model to reason before returning its answer.",
        )
        st.toggle(
            "See source",
            key="show_source",
            help="Show generated SQL, query metrics, and returned rows.",
        )

        sessions = _load_sessions(client)
        connection_error = st.session_state.get("connection_error")
        if connection_error:
            st.markdown(
                '<div class="ppqa-health-bad">API unavailable</div>',
                unsafe_allow_html=True,
            )
            st.caption(SERVICE_UNAVAILABLE_MESSAGE)
        else:
            st.markdown(
                '<div class="ppqa-health-ok">API connected</div>',
                unsafe_allow_html=True,
            )
        if st.session_state.get("sidebar_action_error"):
            st.warning(SERVICE_UNAVAILABLE_MESSAGE)

        st.divider()

        st.button(
            "New chat",
            width="stretch",
            type="primary",
            disabled=analysis_running,
            on_click=_start_new_chat,
        )

        history_cols = st.columns([0.65, 0.35], vertical_alignment="center")
        history_cols[0].caption("Chat history")
        history_cols[1].button(
            "Refresh",
            key="refresh-sessions",
            icon=":material/refresh:",
            type="tertiary",
            disabled=analysis_running,
            on_click=_refresh_sessions,
            args=(client,),
            width="stretch",
        )

        session_limit = int(st.session_state.sidebar_session_limit)
        for session in sessions[:session_limit]:
            _render_session_row(
                client,
                session,
                disabled=analysis_running,
            )

        if len(sessions) > session_limit:
            remaining = len(sessions) - session_limit
            st.button(
                f"Show more ({remaining})",
                key="show-more-sessions",
                width="stretch",
                disabled=analysis_running,
                on_click=_show_more_sessions,
            )


def _render_session_row(
    client: ApiClient,
    session: dict[str, Any],
    *,
    disabled: bool,
) -> None:
    session_id = session["id"]
    is_active = st.session_state.active_session_id == session_id
    title = session.get("title") or "New chat"
    max_title_length = 30 if is_active else 38
    label = (
        title
        if len(title) <= max_title_length
        else f"{title[: max_title_length - 3].rstrip()}..."
    )
    if is_active:
        label = f"Active: {label}"

    cols = st.sidebar.columns([0.72, 0.28], gap="small")
    cols[0].button(
        label,
        key=f"select-{session_id}",
        help=title,
        width="stretch",
        disabled=disabled,
        on_click=_select_session,
        args=(session_id,),
    )
    cols[1].button(
        "Delete",
        key=f"delete-{session_id}",
        help=f"Delete {title}",
        icon=":material/delete:",
        type="tertiary",
        width="stretch",
        disabled=disabled,
        on_click=_delete_session,
        args=(client, session_id),
    )
    st.sidebar.markdown(
        f'<div class="ppqa-session-meta">{session.get("message_count", 0)} messages</div>',
        unsafe_allow_html=True,
    )


def _render_header(
    session_detail: dict[str, Any] | None,
    *,
    analysis_running: bool,
) -> None:
    if session_detail:
        session = session_detail["session"]
        title = session.get("title") or "New chat"
        subtitle = (
            "Analysis in progress"
            if analysis_running
            else _message_count_label(session.get("message_count", 0))
        )
    else:
        title = "New chat"
        subtitle = "Analysis in progress" if analysis_running else "Draft session"
    st.markdown(
        f"""
        <div class="ppqa-header">
          <div class="ppqa-title">{_html_escape(title)}</div>
          <div class="ppqa-subtitle">{_html_escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state() -> None:
    st.markdown(
        """
        <div class="ppqa-empty">
          <div class="ppqa-empty-inner">
            <div class="ppqa-empty-kicker">Performance Planning</div>
            <div class="ppqa-empty-title">Start a new analysis</div>
            <div class="ppqa-empty-copy">
              Postpaid base, sales, churn, and monthly revenue are ready for review.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_messages(
    messages: list[dict[str, Any]],
    *,
    session_id: str,
) -> None:
    limit = int(
        st.session_state.message_render_limits.get(
            session_id,
            INITIAL_RENDERED_MESSAGES,
        )
    )
    hidden_count = max(0, len(messages) - limit)
    if hidden_count:
        st.button(
            f"Show {min(hidden_count, MESSAGE_RENDER_BATCH)} earlier messages",
            key=f"show-earlier-{session_id}-{limit}",
            type="tertiary",
            on_click=_show_more_messages,
            args=(session_id,),
        )

    for message in messages[-limit:]:
        role = message.get("role", "assistant")
        metadata = message.get("metadata") or {}
        content = message.get("content") or ""
        if role == "assistant" and metadata.get("error"):
            # Older persisted messages may contain technical failure details in
            # their content. Never replay those details to the user.
            content = ANALYSIS_UNAVAILABLE_MESSAGE
        with st.chat_message(role, avatar=_message_avatar(role)):
            st.markdown(content)
            if role == "assistant":
                _render_assistant_artifacts(
                    metadata,
                    chart_key=message.get("id"),
                )


def _render_assistant_artifacts(
    metadata: dict[str, Any],
    *,
    chart_key: str | None = None,
) -> None:
    sql = metadata.get("sql")
    query_result = metadata.get("query_result")

    _render_reasoning(metadata.get("reasoning"))
    _render_chart(metadata.get("chart"), chart_key=chart_key)
    _render_csv_download(
        metadata.get("csv_export"),
        artifact_key=chart_key,
    )
    if not st.session_state.get("show_source", False):
        return
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
            preview_rows = rows[:MAX_RENDERED_RESULT_ROWS]
            st.dataframe(preview_rows, width="stretch", hide_index=True)
            if len(rows) > len(preview_rows):
                st.caption(
                    f"Showing {len(preview_rows):,} of {len(rows):,} returned rows "
                    "to keep the browser responsive."
                )


def _render_csv_download(
    export: Any,
    *,
    artifact_key: str | None,
) -> None:
    """Render a persistent download button only after CSV was requested."""

    if not isinstance(export, dict) or export.get("status") != "ready":
        return
    try:
        csv_data = csv_export_to_bytes(export)
    except (TypeError, ValueError):
        logger.warning("Could not serialize persisted result as CSV", exc_info=True)
        return

    filename = str(export.get("filename") or "performance-planning-data.csv").strip()
    if not filename.lower().endswith(".csv"):
        filename = "performance-planning-data.csv"
    rows = export.get("rows")
    row_count = len(rows) if isinstance(rows, list) else 0
    label = f"Download CSV ({row_count:,} rows)"
    st.download_button(
        label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        key=f"csv-download-{artifact_key or filename}",
        icon=":material/download:",
        on_click="ignore",
    )


def _render_reasoning(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    with st.expander("Thinking — click to view", expanded=False):
        with st.container(height=280, border=False):
            st.markdown(value)


def _render_chart(chart: Any, *, chart_key: str | None = None) -> None:
    if not isinstance(chart, dict):
        return
    version = chart.get("version")
    if version != 1 and version != "1":
        return

    chart_type = chart.get("type")
    if not isinstance(chart_type, str):
        return
    chart_type = chart_type.strip().lower()
    if chart_type not in {"line", "bar", "area", "scatter", "pie", "donut"}:
        return

    raw_data = chart.get("data")
    if not isinstance(raw_data, list):
        return
    rows = [row for row in raw_data if isinstance(row, dict)]
    if not rows:
        return

    fields = {field for row in rows for field in row if isinstance(field, str)}
    x_field = chart.get("x")
    if (
        not isinstance(x_field, str)
        or not x_field.strip()
        or x_field not in fields
        or not any(row.get(x_field) is not None for row in rows)
    ):
        return

    raw_y_fields = chart.get("y")
    if not isinstance(raw_y_fields, list):
        return
    y_fields: list[str] = []
    for field in raw_y_fields:
        if (
            isinstance(field, str)
            and field.strip()
            and field in fields
            and field not in y_fields
            and any(row.get(field) is not None for row in rows)
        ):
            y_fields.append(field)
    if not y_fields:
        return

    x_kind = chart.get("x_kind", "nominal")
    if not isinstance(x_kind, str) or x_kind not in {
        "temporal",
        "quantitative",
        "nominal",
    }:
        return

    series_field = chart.get("series")
    if (
        not isinstance(series_field, str)
        or series_field not in fields
        or not any(row.get(series_field) is not None for row in rows)
    ):
        series_field = None

    folded = len(y_fields) > 1
    metric_field = _unused_chart_field("__ppqa_metric", fields)
    value_field = _unused_chart_field("__ppqa_value", fields | {metric_field})
    plotted_y_field = value_field if folded else y_fields[0]

    spec: dict[str, Any] = {} if folded else {"height": 360}
    spec["background"] = "#FFFFFF"
    spec["config"] = {
        "range": {"category": list(STC_CHART_COLORS)},
        "axis": {
            "domainColor": "#D9DEE7",
            "gridColor": "#E5E8EF",
            "labelColor": "#5B667A",
            "titleColor": "#1D252D",
        },
        "legend": {
            "labelColor": "#5B667A",
            "titleColor": "#1D252D",
        },
        "title": {"color": "#1D252D", "fontSize": 18},
        "view": {"stroke": None},
    }
    title = chart.get("title")
    if isinstance(title, str) and title.strip():
        spec["title"] = title.strip()
    if folded:
        spec["transform"] = [
            {"fold": y_fields, "as": [metric_field, value_field]},
        ]

    rendered_x_kind, rendered_x_sort = _vega_x_kind(rows, x_field, x_kind)
    x_encoding: dict[str, Any] = {
        "field": x_field,
        "type": rendered_x_kind,
        "title": _chart_field_title(x_field),
    }
    if rendered_x_sort is not None:
        x_encoding["sort"] = rendered_x_sort
    temporal_format = None
    if x_kind == "temporal":
        temporal_values = list(
            dict.fromkeys(row.get(x_field) for row in rows if row.get(x_field) is not None)
        )
        temporal_format = _temporal_axis_format(temporal_values)
        x_axis: dict[str, Any] = {
            "labelAngle": -30,
            "tickCount": max(2, min(len(temporal_values), 12)),
        }
        if temporal_format is not None:
            x_axis["format"] = temporal_format
            x_encoding["timeUnit"] = "yearmonth"
        x_encoding["axis"] = x_axis

    value_title = "Value" if folded else _chart_field_title(y_fields[0])
    x_tooltip: dict[str, Any] = {
        "field": x_field,
        "type": rendered_x_kind,
        "title": _chart_field_title(x_field),
    }
    if temporal_format is not None:
        x_tooltip["timeUnit"] = "yearmonth"
        x_tooltip["format"] = temporal_format
    tooltip: list[dict[str, Any]] = [x_tooltip]
    if series_field and series_field != x_field:
        tooltip.append(
            {
                "field": series_field,
                "type": "nominal",
                "title": _chart_field_title(series_field),
            }
        )
    if folded:
        tooltip.append({"field": metric_field, "type": "nominal", "title": "Metric"})
    tooltip.append(
        {"field": plotted_y_field, "type": "quantitative", "title": value_title}
    )

    if chart_type in {"pie", "donut"}:
        mark: dict[str, Any] = {"type": "arc"}
        if chart_type == "donut":
            mark["innerRadius"] = 65

        color_field = series_field or x_field
        encoding: dict[str, Any] = {
            "theta": {"field": plotted_y_field, "type": "quantitative"},
            "color": {
                "field": color_field,
                "type": "nominal",
                "title": _chart_field_title(color_field),
                "scale": {"range": list(STC_CHART_COLORS)},
            },
            "tooltip": tooltip,
        }
        if series_field and series_field != x_field:
            encoding["detail"] = {"field": x_field, "type": "nominal"}

        chart_body = {"mark": mark, "encoding": encoding}
        if folded:
            chart_body["height"] = 360
            spec["facet"] = {
                "column": {"field": metric_field, "type": "nominal", "title": None}
            }
            spec["spec"] = chart_body
        else:
            spec.update(chart_body)
    else:
        mark = {
            "line": {
                "type": "line",
                "color": STC_CHART_COLORS[0],
                "strokeWidth": 3,
                "point": {"filled": True, "size": 70},
            },
            "bar": {"type": "bar", "color": STC_CHART_COLORS[0]},
            "area": {
                "type": "area",
                "color": STC_CHART_COLORS[0],
                "opacity": 0.45,
                "line": True,
            },
            "scatter": {
                "type": "point",
                "color": STC_CHART_COLORS[0],
                "filled": True,
                "size": 80,
            },
        }[chart_type]
        y_encoding: dict[str, Any] = {
            "field": plotted_y_field,
            "type": "quantitative",
            "title": value_title,
            "axis": {"format": "~s"},
        }
        if chart_type == "line":
            y_encoding["scale"] = {"zero": False, "nice": True}
        encoding = {
            "x": x_encoding,
            "y": y_encoding,
            "tooltip": tooltip,
        }

        color_field = series_field
        if color_field:
            encoding["color"] = {
                "field": color_field,
                "type": "nominal",
                "title": _chart_field_title(color_field),
                "scale": {"range": list(STC_CHART_COLORS)},
            }
            if chart_type == "bar":
                encoding["xOffset"] = {
                    "field": color_field,
                    "type": "nominal",
                }
        chart_body = {"mark": mark, "encoding": encoding}
        if folded:
            chart_body["height"] = 360
            spec["facet"] = {
                "column": {"field": metric_field, "type": "nominal", "title": None}
            }
            spec["resolve"] = {"scale": {"y": "independent"}}
            spec["spec"] = chart_body
        else:
            spec.update(chart_body)

    key = f"chart-{chart_key}" if chart_key else None
    st.vega_lite_chart(
        rows,
        spec=spec,
        width="stretch",
        key=key,
    )

    notes = []
    fallback_reason = chart.get("fallback_reason")
    requested_type = chart.get("requested_type")
    if isinstance(fallback_reason, str) and fallback_reason.strip():
        notes.append(" ".join(fallback_reason.split())[:500])
    elif (
        isinstance(requested_type, str)
        and requested_type in {"line", "bar", "area", "scatter", "pie", "donut"}
        and requested_type != chart_type
    ):
        notes.append(
            f"Shown as a {chart_type} chart because these values do not support "
            f"a {requested_type} chart."
        )
    if notes:
        st.caption(" ".join(notes))


def _unused_chart_field(base: str, fields: set[str]) -> str:
    candidate = base
    while candidate in fields:
        candidate = f"_{candidate}"
    return candidate


def _temporal_axis_format(values: list[Any]) -> str | None:
    """Use one readable month tick for result sets containing one row per month."""

    if not values or not all(
        isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip())
        for value in values
    ):
        return None
    months = {value.strip()[:7] for value in values}
    return "%b %Y" if len(months) == len(values) else None


def _chart_field_title(field: str) -> str:
    return " ".join(field.replace("_", " ").split()).title() or field


def _vega_x_kind(
    rows: list[dict[str, Any]],
    field: str,
    declared_kind: str,
) -> tuple[str, list[Any] | None]:
    """Use an ordinal axis for ordered period labels Vega cannot parse as dates."""

    if declared_kind != "temporal":
        return declared_kind, None

    values = [row.get(field) for row in rows if row.get(field) is not None]
    if values and all(
        isinstance(value, str) and _ISO_TEMPORAL_RE.fullmatch(value.strip())
        for value in values
    ):
        return "temporal", None

    ordered_values: list[Any] = []
    for value in values:
        if value not in ordered_values:
            ordered_values.append(value)
    return "ordinal", ordered_values


@st.fragment
def _render_question_composer() -> None:
    """Rerun only the composer when the user submits a question."""

    with st.bottom:
        submission = st.chat_input(
            "Ask a performance planning question",
            key="question-composer",
            max_chars=MAX_QUESTION_CHARS,
            submit_mode="disable",
        )
    if submission is None:
        return
    prompt = submission.strip()
    if not prompt:
        return
    _begin_analysis(prompt)


def _begin_analysis(prompt: str) -> None:
    client = _get_api_client(st.session_state.api_base_url)
    runner = _get_analysis_runner()
    if runner.active_job() is not None:
        st.rerun()
    session_id = st.session_state.get("active_session_id")
    dry_run = bool(st.session_state.get("dry_run", False))
    enable_thinking = bool(st.session_state.get("enable_thinking", True))
    st.session_state.failed_analysis = None

    if not session_id:
        try:
            session = client.create_session()
        except ApiError as exc:
            _record_failed_analysis(None, prompt, dry_run, exc)
            st.rerun()
        if not isinstance(session, dict) or not session.get("id"):
            _record_failed_analysis(
                None,
                prompt,
                dry_run,
                ApiError("API returned an invalid chat session"),
            )
            st.rerun()
        session_id = str(session["id"])
        _cache_new_session(session)

    try:
        runner.start(
            base_url=client.base_url,
            session_id=session_id,
            question=prompt,
            dry_run=dry_run,
            enable_thinking=enable_thinking,
        )
    except Exception as exc:
        _record_failed_analysis(session_id, prompt, dry_run, exc)
    st.rerun()


@st.fragment(run_every=0.75)
def _render_active_analysis() -> None:
    """Poll a background request without rebuilding the saved conversation."""

    runner = _get_analysis_runner()
    job = runner.active_job()
    if job is None:
        st.rerun()

    snapshot = job.snapshot()
    if snapshot.done:
        try:
            response = job.result()
            _apply_analysis_response(
                response,
                expected_session_id=snapshot.session_id,
                reasoning=snapshot.reasoning,
            )
        except AnalysisCancelled:
            st.session_state.analysis_notice = "Analysis stopped"
        except Exception as exc:
            _record_failed_analysis(
                snapshot.session_id,
                snapshot.question,
                job.dry_run,
                exc,
            )
        finally:
            runner.clear(snapshot.job_id)
            st.session_state.pop(f"thinking-expanded-{snapshot.job_id}", None)
            st.session_state.pop(f"thinking-toggle-{snapshot.job_id}", None)
        st.rerun()

    with st.chat_message("user", avatar=_message_avatar("user")):
        st.markdown(snapshot.question)

    with st.chat_message("assistant", avatar=_message_avatar("assistant")):
        with st.container(key="live-thinking"):
            is_expanded = False
            if job.enable_thinking:
                expanded_key = f"thinking-expanded-{snapshot.job_id}"
                is_expanded = bool(st.session_state.get(expanded_key, False))
                if st.button(
                    "Click to hide thinking" if is_expanded else "Click to view thinking",
                    key=f"thinking-toggle-{snapshot.job_id}",
                    help="Click to show or hide live reasoning",
                    type="tertiary",
                    icon=":material/progress_activity:",
                ):
                    is_expanded = not is_expanded
                    st.session_state[expanded_key] = is_expanded
                st.caption(snapshot.progress)
            else:
                st.markdown(
                    (
                        '<div class="ppqa-non-thinking-progress" role="status" '
                        'aria-live="polite">'
                        '<span class="ppqa-progress-spinner" aria-hidden="true"></span>'
                        f"<span>{html.escape(snapshot.progress)}</span>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
            if is_expanded:
                with st.container(
                    key="live-thinking-content",
                    height=280,
                    border=True,
                    autoscroll=True,
                ):
                    if snapshot.reasoning:
                        st.markdown(snapshot.reasoning)
                    else:
                        st.write(snapshot.progress)

    with st.bottom:
        with st.container(key="active-composer"):
            st.chat_input(
                (
                    "Stopping analysis…"
                    if snapshot.stopping
                    else "Analysis in progress…"
                ),
                key="active-question-composer",
                disabled=True,
            )
            if st.button(
                "Stop",
                key="stop-analysis",
                help="Stop the current analysis",
                disabled=snapshot.stopping,
                type="primary",
                icon=":material/stop:",
            ):
                if runner.cancel(snapshot.job_id):
                    st.session_state.analysis_notice = "Analysis stopped"
                st.rerun()


def _cache_new_session(session: dict[str, Any]) -> None:
    session_id = str(session["id"])
    st.session_state.active_session_id = session_id
    details = dict(st.session_state.get("session_details", {}))
    details[session_id] = {"session": session, "messages": []}
    st.session_state.session_details = details
    st.session_state.connection_error = None
    _upsert_session_summary(session)


def _apply_analysis_response(
    response: dict[str, Any],
    *,
    expected_session_id: str,
    reasoning: str = "",
) -> None:
    session = response.get("session")
    user_message = response.get("user_message")
    assistant_message = response.get("assistant_message")
    if not all(
        isinstance(item, dict)
        for item in (session, user_message, assistant_message)
    ):
        raise ApiError("API returned an incomplete analysis response")

    if reasoning.strip():
        assistant_message = dict(assistant_message)
        metadata = dict(assistant_message.get("metadata") or {})
        metadata["reasoning"] = reasoning
        assistant_message["metadata"] = metadata

    session_id = str(session.get("id") or "")
    if not session_id or session_id != expected_session_id:
        raise ApiError("API returned an analysis for the wrong chat session")

    details = dict(st.session_state.get("session_details", {}))
    current_detail = details.get(session_id) or {"session": session, "messages": []}
    messages = list(current_detail.get("messages") or [])
    existing_ids = {message.get("id") for message in messages}
    for message in (user_message, assistant_message):
        if message.get("id") not in existing_ids:
            messages.append(message)
            existing_ids.add(message.get("id"))
    details[session_id] = {"session": session, "messages": messages}
    st.session_state.session_details = details
    st.session_state.active_session_id = session_id
    st.session_state.failed_analysis = None
    st.session_state.connection_error = None
    _upsert_session_summary(session)


def _upsert_session_summary(session: dict[str, Any]) -> None:
    session_id = session.get("id")
    sessions = st.session_state.get("sessions_cache") or []
    st.session_state.sessions_cache = [
        session,
        *[item for item in sessions if item.get("id") != session_id],
    ]


def _record_failed_analysis(
    session_id: str | None,
    question: str,
    dry_run: bool,
    error: Exception,
) -> None:
    _log_frontend_error("Analysis request failed", error)
    st.session_state.failed_analysis = {
        "session_id": session_id,
        "question": question,
        "dry_run": dry_run,
        "error": ANALYSIS_UNAVAILABLE_MESSAGE,
    }


def _render_failed_analysis() -> None:
    failure = st.session_state.get("failed_analysis")
    if not isinstance(failure, dict):
        return
    with st.chat_message("user", avatar=_message_avatar("user")):
        st.markdown(str(failure.get("question") or ""))
    with st.chat_message("assistant", avatar=_message_avatar("assistant")):
        st.markdown(ANALYSIS_UNAVAILABLE_MESSAGE)


def _log_frontend_error(context: str, error: Exception) -> None:
    """Keep technical diagnostics in logs without exposing them in Streamlit."""

    traceback = error.__traceback__
    exc_info = (type(error), error, traceback) if traceback is not None else False
    logger.error("%s: %s", context, error, exc_info=exc_info)


def _message_avatar(role: str) -> str:
    if role == "user":
        return ":material/account_circle:"
    return ":material/query_stats:"


def _message_count_label(count: int) -> str:
    if count == 1:
        return "1 saved message"
    return f"{count} saved messages"


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
