"""Streamlit frontend for the Performance Planning Q&A backend."""

from __future__ import annotations

import os
import re
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from styles import APP_CSS


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
MAX_RENDERED_CHART_ROWS = 500
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

    prompt = _render_question_composer()
    if prompt:
        _submit_prompt(client, prompt)


def _init_state() -> None:
    st.session_state.setdefault(
        "api_base_url",
        os.getenv("PPQA_API_BASE_URL", DEFAULT_API_BASE_URL),
    )
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("dry_run", False)
    st.session_state.setdefault("show_source", False)


def _sidebar() -> ApiClient:
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
        api_base_url = st.text_input("API URL", key="api_base_url")
        st.toggle("Dry run", key="dry_run", help="Generate SQL without executing it.")
        st.toggle(
            "See source",
            key="show_source",
            help="Show generated SQL, query metrics, and returned rows.",
        )
        client = ApiClient(api_base_url)

        try:
            client.health()
            st.markdown('<div class="ppqa-health-ok">API connected</div>', unsafe_allow_html=True)
        except ApiError as exc:
            st.markdown('<div class="ppqa-health-bad">API unavailable</div>', unsafe_allow_html=True)
            st.caption(str(exc))

        st.divider()

        if st.button("New chat", width="stretch", type="primary"):
            st.session_state.active_session_id = None
            st.rerun()

        st.caption("Chat history")
        try:
            sessions = client.list_sessions()
        except ApiError as exc:
            st.error(str(exc))
            sessions = []

        for session in sessions:
            _render_session_row(client, session)

    return client


def _render_session_row(client: ApiClient, session: dict[str, Any]) -> None:
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

    cols = st.sidebar.columns([0.78, 0.22], gap="small")
    if cols[0].button(label, key=f"select-{session_id}", width="stretch"):
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
        subtitle = _message_count_label(session.get("message_count", 0))
    else:
        title = "New chat"
        subtitle = "Draft session"
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


def _render_messages(messages: list[dict[str, Any]]) -> None:
    if not messages:
        _render_empty_state()
        return

    for message in messages:
        role = message.get("role", "assistant")
        with st.chat_message(role, avatar=_message_avatar(role)):
            st.markdown(message.get("content") or "")
            if role == "assistant":
                _render_assistant_artifacts(
                    message.get("metadata") or {},
                    chart_key=message.get("id"),
                )


def _render_assistant_artifacts(
    metadata: dict[str, Any],
    *,
    chart_key: str | None = None,
) -> None:
    sql = metadata.get("sql")
    error = metadata.get("error")
    query_result = metadata.get("query_result")

    if error:
        st.error(error)
    _render_chart(metadata.get("chart"), chart_key=chart_key)
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
            st.dataframe(rows, width="stretch", hide_index=True)


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
    valid_rows = [row for row in raw_data if isinstance(row, dict)]
    frontend_truncated = len(valid_rows) > MAX_RENDERED_CHART_ROWS
    rows = valid_rows[:MAX_RENDERED_CHART_ROWS]
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
    if chart.get("truncated") is True or frontend_truncated:
        notes.append("Chart data was truncated to keep the visualization readable.")
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


def _render_question_composer() -> str | None:
    submission = st.chat_input("Ask a performance planning question")
    if submission is None:
        return None
    prompt = submission.strip()
    return prompt or None


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

    with st.chat_message("user", avatar=_message_avatar("user")):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=_message_avatar("assistant")):
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
        _render_assistant_artifacts(
            assistant_message.get("metadata") or {},
            chart_key=assistant_message.get("id"),
        )

    st.rerun()


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
