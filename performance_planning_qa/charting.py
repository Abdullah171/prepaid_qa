"""Question-gated, renderer-neutral chart specifications.

The chart builder deliberately treats an LLM plan as a set of field references,
never as a source of chart values.  Every value in :class:`ChartSpec.data` is
materialized from the current :class:`~performance_planning_qa.database.QueryResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
import math
import re
from typing import Any, Literal, Mapping, Sequence

from performance_planning_qa.database import QueryResult


ChartType = Literal["line", "bar", "area", "scatter", "pie", "donut"]
XKind = Literal["temporal", "quantitative", "nominal"]
ChartTrigger = Literal["explicit", "trend"]

ALLOWED_CHART_TYPES: frozenset[str] = frozenset(
    {"line", "bar", "area", "scatter", "pie", "donut"}
)

_EXPLICIT_CHART_RE = re.compile(
    r"\b(?:charts?|graphs?|plots?|plotting|plotted|visuals?|visually|"
    r"visuali[sz](?:e|ed|ing|ation|ations)|diagrams?)\b",
    re.IGNORECASE,
)
_CHART_TERM_TYPO_RE = re.compile(
    r"\b(?:agraph|achart|aplot|garph|grahp|graoph|grapgh|grpah|grph|grah|charth|chartt|"
    r"visulization|visulisation|visualiztion|visualisaton)\b",
    re.IGNORECASE,
)
_TREND_RE = re.compile(
    r"(?:"
    r"\btrend(?:s|ing|ed)?\b|\btime[\s-]*series\b|\bover\s+time\b|\btrajectory\b|"
    r"\bevolution\b|\b(?:daily|weekly|monthly|quarterly|yearly|annually)\b|"
    r"\bby\s+(?:day|week|month|quarter|year)s?\b|"
    r"\b(?:per|each)\s+(?:day|week|month|quarter|year)\b|"
    r"\bacross\s+(?:days|weeks|months|quarters|years)\b|"
    r"\b(?:day|week|month|quarter|year)[\s-]*over[\s-]*(?:day|week|month|quarter|year)\b|"
    r"\b(?:wow|mom|qoq|yoy)\b"
    r")",
    re.IGNORECASE,
)
_NO_CHART_RE = re.compile(
    r"(?:"
    r"\b(?:no|without)\s+(?:a\s+)?(?:visual|diagram)s?\b|"
    r"\bwithout\s+(?:showing|making|creating|drawing|including)\s+"
    r"(?:a\s+)?(?:visual|diagram)s?\b|"
    r"\b(?:do\s+not|don['’]?t)\s+(?:show|make|create|generate|render|display|"
    r"include|draw)\s+(?:me\s+)?(?:a\s+)?(?:visual|diagram)s?\b|"
    r"\b(?:no|without)\s+(?:a\s+)?(?:chart|graph|plot|visuali[sz]ation)s?\b|"
    r"\bwithout\s+(?:showing|making|creating|drawing|plotting|graphing|including)\s+"
    r"(?:a\s+)?(?:chart|graph|plot|visuali[sz]ation)s?\b|"
    r"\b(?:do\s+not|don['’]?t)\s+(?:"
    r"(?:plot|graph|chart|visuali[sz]e)\b|"
    r"(?:show|make|create|generate|render|display|include|draw)\s+(?:me\s+)?"
    r"(?:a\s+)?(?:chart|graph|plot|visuali[sz]ation)s?\b"
    r")|"
    r"\b(?:not|instead\s+of)\s+(?:a\s+)?(?:chart|graph|plot|visuali[sz]ation)s?\b|"
    r"\b(?:text|table)[\s-]*only\b|"
    r"\bonly\s+(?:text|a\s+table|the\s+table)\b|"
    r"\bjust\s+(?:text|a\s+table|the\s+table)\b"
    r")",
    re.IGNORECASE,
)
_TABLE_PRESENTATION_RE = re.compile(
    r"\b(?:as|in)\s+(?:a\s+)?table\b|"
    r"\b(?:table|tabular)\s+format\b|"
    r"\bin\s+tabular\s+form\b|"
    r"\b(?:show|display|render|present|return|give)\s+(?:me\s+)?"
    r"(?:(?:it|that|this)\s+)?(?:(?:as|in)\s+)?(?:a|the)\s+table\b",
    re.IGNORECASE,
)
_TEXT_PRESENTATION_RE = re.compile(
    r"\b(?:as|in)\s+(?:plain\s+)?text\b|"
    r"\b(?:as|in)\s+prose\b|"
    r"\b(?:written|narrative|textual)\s+(?:summary|format|form)\b|"
    r"\b(?:show|display|render|present|return|give)\s+(?:me\s+)?"
    r"(?:(?:it|that|this)\s+)?(?:(?:as|in)\s+)?(?:plain\s+text|prose)\b",
    re.IGNORECASE,
)

_ANAPHORIC_TYPE_RE = re.compile(
    r"\b(?:"
    r"(?:make|show|render|display)\s+{reference}\s+(?:as\s+)?(?:an?\s+)?|"
    r"(?:change|switch|convert|turn)\s+{reference}\s+(?:to|into|as)\s+(?:an?\s+)?"
    r")"
    r"(?P<type>line|bar|column|area|scatter\s*plot|scatter|pie|donut|doughnut|ring)"
    r"(?=\s*(?:(?:chart|graph|plot)\s*)?(?:instead|please|now)?[?.!]*$)".format(
        reference=(
            r"(?:it|that|this|the\s+(?:chart|graph|plot|result)|"
            r"(?:the\s+)?(?:previous|prior|above)(?:\s+(?:chart|graph|plot|result))?)"
        )
    ),
    re.IGNORECASE,
)

_USER_TYPE_PATTERNS: tuple[tuple[ChartType, re.Pattern[str]], ...] = (
    (
        "donut",
        re.compile(
            r"\b(?:donut|doughnut|ring)\s+(?:chart|graph|plot)\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:a\s+)?(?:donut|doughnut)\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:a\s+)?(?:donut|doughnut)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pie",
        re.compile(
            r"\bpie\s+(?:chart|graph|plot)\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:a\s+)?pie\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:a\s+)?pie\b",
            re.IGNORECASE,
        ),
    ),
    (
        "scatter",
        re.compile(
            r"\bscatter\s*(?:plot|chart|graph)\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:a\s+)?scatter(?:\s*plot)?\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:a\s+)?scatter(?:\s*plot)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "area",
        re.compile(
            r"\barea\s+(?:chart|graph|plot)\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:an?\s+)?area\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:an?\s+)?area\b",
            re.IGNORECASE,
        ),
    ),
    (
        "bar",
        re.compile(
            r"\b(?:grouped\s+)?bar\s+(?:chart|graph|plot)\b|"
            r"\bcolumn\s+(?:chart|graph|plot)\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:a\s+)?(?:bar|column)\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:a\s+)?(?:bar|column)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "line",
        re.compile(
            r"\bline\s*(?:chart|graph|plot)\b|\btrend\s*line\b|"
            r"\b(?:it|that|this)\s+(?:as|into)\s+(?:a\s+)?line\b|"
            r"\bmake\s+(?:it|that|this)\s+(?:a\s+)?line\b",
            re.IGNORECASE,
        ),
    ),
)

_UNSUPPORTED_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "horizontal bar",
        re.compile(
            r"\bhorizontal\s+bar(?:\s+(?:chart|graph|plot))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stacked bar",
        re.compile(
            r"\bstacked\s+bar(?:\s+(?:chart|graph|plot))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stacked area",
        re.compile(
            r"\bstacked\s+area(?:\s+(?:chart|graph|plot))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "waterfall",
        re.compile(
            r"\bwaterfall(?:\s+(?:chart|graph|plot))?\b",
            re.IGNORECASE,
        ),
    ),
    ("histogram", re.compile(r"\bhistograms?\b", re.IGNORECASE)),
    (
        "bubble",
        re.compile(r"\bbubble\s+(?:chart|graph|plot)\b", re.IGNORECASE),
    ),
    (
        "funnel",
        re.compile(r"\bfunnel\s+(?:chart|graph|plot)\b", re.IGNORECASE),
    ),
    (
        "radar",
        re.compile(r"\bradar\s+(?:chart|graph|plot)\b", re.IGNORECASE),
    ),
    ("heatmap", re.compile(r"\bheat[\s-]*maps?\b", re.IGNORECASE)),
    (
        "box plot",
        re.compile(
            r"\bbox(?:[\s-]+and[\s-]+whisker|[\s-]+plots?)\b",
            re.IGNORECASE,
        ),
    ),
)

_TEMPORAL_FIELD_RE = re.compile(
    r"(?:^|_)(?:date|datetime|timestamp|time|day|week|month|quarter|year|period)(?:$|_)",
    re.IGNORECASE,
)
_IDENTIFIER_FIELD_RE = re.compile(
    r"(?:^|_)(?:id|key|number|num|nmb|nmbr|msisdn|account|acct|accnt|phone|"
    r"user|usr)(?:$|_)",
    re.IGNORECASE,
)
_ACCESS_METHOD_IDENTIFIER_RE = re.compile(
    r"^(?:.*_)?(?:accs?_?meth(?:od)?|access_?meth(?:od)?)"
    r"(?:_(?:val|value|num|number|id|key))?$",
    re.IGNORECASE,
)
_SAFE_IDENTIFIER_AGGREGATE_RE = re.compile(
    r"^(?:"
    r"(?:count|cnt)(?:_of)?_(?:(?:distinct|unique)_)?[a-z][a-z0-9_]*|"
    r"(?:(?:total|sum|avg|average|min|max)_)?"
    r"(?:number|num|nmb|nmbr)_of_[a-z][a-z0-9_]*|"
    r"(?:(?:total|sum|avg|average|min|max)_)?[a-z][a-z0-9_]*_"
    r"(?:count|cnt|rate|pct|percent|ratio|share|revenue|amount)"
    r")$",
    re.IGNORECASE,
)
_BARE_ROW_IDENTIFIER_ALIAS_RE = re.compile(
    r"^(?:lines?|mobiles?|subscribers?|subscriptions?|customers?|part(?:y|ies)|"
    r"subs?|cli|mdn|imsi|imei)$",
    re.IGNORECASE,
)
_NAMED_ROW_IDENTIFIER_ALIAS_RE = re.compile(
    r"^(?:lines?|mobiles?|customers?|cust|subscribers?|subscriptions?|"
    r"part(?:y|ies)|accounts?|acct|users?|agents?|orders?|service_?orders?|"
    r"subs|phone|msisdn|cli|mdn|imsi|imei)"
    r"_?(?:no|num|number|id|key|name|value|val|code)$",
    re.IGNORECASE,
)
_SAFE_PERIOD_ALIAS_RE = re.compile(
    r"^(?:(?:calendar|fiscal|reporting|sales|churn|ref)_)?"
    r"(?:month|week|quarter|day|year)_(?:num|number)$",
    re.IGNORECASE,
)
_SAFE_ENTITY_AGGREGATE_RE = re.compile(
    r"^(?:"
    r"(?:count|cnt|number|num|nmb|nmbr)(?:_of)?_(?:distinct_|unique_)?"
    r"(?:lines|mobiles|subscribers|subscriptions|customers|parties)|"
    r"(?:lines?|mobiles?|subscribers?|subscriptions?|customers?|part(?:y|ies))_"
    r"(?:count|cnt)|"
    r"(?:active|inactive|unique|distinct|churned|new|lost|retained|activated|"
    r"deactivated|cancelled|terminated|total)_"
    r"(?:lines|mobiles|subscribers|subscriptions|customers|parties)"
    r")$",
    re.IGNORECASE,
)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_HTML_BRACKET_RE = re.compile(r"[<>]")
_UNSAFE_RENDER_FIELD_RE = re.compile(r"[.\[\]\\]")
_FOLLOWUP_TRANSFORM_RE = re.compile(
    r"(?:"
    r"\b(?:only|except|excluding|filter|filtered|where)\b|"
    r"\b(?:by|per|each|across|group|grouped|breakdown)\b|"
    r"\b(?:daily|weekly|monthly|quarterly|yearly|annually)\b|"
    r"\b(?:compare|comparison|versus|vs\.?|add|include|remove)\b|"
    r"\b(?:top|bottom|sort|sorted|order|ordered|descending|ascending)\b|"
    r"\b(?:day|week|month|quarter|year)s?\b|"
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b|"
    r"\b(?:19|20)\d{2}\b|\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b|"
    r"\bQ[1-4]\b"
    r")",
    re.IGNORECASE,
)
_MONTH_NUMBERS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_PRESENTATION_ONLY_TOKENS = frozenset(
    {
        "a",
        "again",
        "also",
        "an",
        "area",
        "as",
        "above",
        "bar",
        "can",
        "change",
        "chart",
        "column",
        "convert",
        "could",
        "csv",
        "data",
        "display",
        "donut",
        "doughnut",
        "download",
        "draw",
        "export",
        "file",
        "format",
        "give",
        "graph",
        "i",
        "in",
        "instead",
        "into",
        "it",
        "line",
        "make",
        "me",
        "need",
        "now",
        "of",
        "pie",
        "please",
        "plot",
        "previous",
        "prior",
        "redo",
        "redraw",
        "render",
        "replot",
        "result",
        "restyle",
        "same",
        "scatter",
        "scatterplot",
        "send",
        "show",
        "switch",
        "that",
        "the",
        "these",
        "this",
        "those",
        "to",
        "turn",
        "use",
        "using",
        "horizontal",
        "ring",
        "visualization",
        "visualize",
        "visualisation",
        "visualise",
        "with",
        "would",
        "want",
        "yeah",
        "yes",
        "you",
    }
)


@dataclass(frozen=True)
class ChartIntent:
    """The small, deterministic decision made from the current question."""

    trigger: ChartTrigger
    requested_type: ChartType | None = None
    unsupported_type: str | None = None


@dataclass(frozen=True)
class ChartSpec:
    """A versioned chart contract that contains data but no renderer details."""

    version: int = field(default=1, init=False)
    type: ChartType
    title: str
    x: str
    y: tuple[str, ...]
    series: str | None
    x_kind: XKind
    trigger: ChartTrigger
    requested_type: ChartType | None
    fallback_reason: str | None
    truncated: bool
    data: list[dict[str, Any]]

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-ready shape expected by an API or chat metadata."""

        return {
            "version": self.version,
            "type": self.type,
            "title": self.title,
            "x": self.x,
            "y": list(self.y),
            "series": self.series,
            "x_kind": self.x_kind,
            "trigger": self.trigger,
            "requested_type": self.requested_type,
            "fallback_reason": self.fallback_reason,
            "truncated": self.truncated,
            "data": [dict(row) for row in self.data],
        }


@dataclass(frozen=True)
class _FieldProfile:
    name: str
    kind: XKind
    non_null_count: int
    numeric_count: int
    distinct_count: int


def detect_chart_intent(question: str) -> ChartIntent | None:
    """Return chart intent only for explicit chart or temporal/trend wording.

    A clear request for text/table-only output always wins, including when the
    same question also contains a trend phrase.
    """

    text = _normalize_chart_term_typos(str(question or "").strip())
    if not text or chart_output_suppressed(text):
        return None

    unsupported_type = _unsupported_type_from_question(text)
    requested_type = (
        None if unsupported_type is not None else _requested_type_from_question(text)
    )
    explicit = (
        bool(_EXPLICIT_CHART_RE.search(text))
        or requested_type is not None
        or unsupported_type is not None
    )
    trend = bool(_TREND_RE.search(text))
    if not explicit and not trend:
        return None

    return ChartIntent(
        trigger="explicit" if explicit else "trend",
        requested_type=requested_type,
        unsupported_type=unsupported_type,
    )


def chart_output_suppressed(question: str) -> bool:
    """Return whether the current turn explicitly asks not to show a chart."""

    text = _normalize_chart_term_typos(str(question or "").strip())
    if not text or _NO_CHART_RE.search(text):
        return True
    return bool(
        (
            _TABLE_PRESENTATION_RE.search(text)
            or _TEXT_PRESENTATION_RE.search(text)
        )
        and not _EXPLICIT_CHART_RE.search(text)
    )


def is_anaphoric_chart_followup(question: str) -> bool:
    """Detect a strong analytical continuation that may inherit a prior chart.

    This deliberately excludes weak references such as "what about churn?".
    The caller must additionally verify that the immediately preceding assistant
    result contains a valid chart before passing inherited intent to the builder.
    """

    text = _normalize_chart_term_typos(
        " ".join(str(question or "").strip().split())
    )
    current_intent = detect_chart_intent(text)
    if (
        not text
        or len(text.split()) > 32
        or _NO_CHART_RE.search(text)
        or _TABLE_PRESENTATION_RE.search(text)
        or _TEXT_PRESENTATION_RE.search(text)
        or (
            current_intent is not None
            and current_intent.requested_type is not None
        )
    ):
        return False

    strong_reference = bool(
        re.search(
            r"\b(?:do|show|run|repeat|apply|give)\s+(?:me\s+)?(?:the\s+)?same\b|"
            r"\b(?:do|show|run|repeat)\s+(?:it|that)\s+again\b|"
            r"\b(?:same|identical)\s+(?:analysis|thing|view|trend|breakdown)\b",
            text,
            re.IGNORECASE,
        )
    )
    analytical_change = bool(
        re.search(
            r"\b(?:for|with|by)\s+(?:the\s+)?(?:[a-z0-9][\w-]*)(?:\s+[a-z0-9][\w-]*)?\b|"
            r"\b(?:apply|applied)\s+(?:it|that|the\s+same)\s+to\s+\w+\b",
            text,
            re.IGNORECASE,
        )
    )
    return strong_reference and analytical_change


def is_chart_only_followup(question: str) -> bool:
    """Identify an anaphoric, presentation-only restyle of a previous result."""

    text = _normalize_chart_term_typos(
        " ".join(str(question or "").strip().split())
    )
    intent = detect_chart_intent(text)
    if intent is None or intent.trigger != "explicit" or len(text.split()) > 24:
        return False

    has_reference = bool(
        re.search(
            r"\b(?:it|that|this|those|these|same|previous|prior|above)\b",
            text,
            re.IGNORECASE,
        )
    )
    if not has_reference:
        return False

    if _FOLLOWUP_TRANSFORM_RE.search(text):
        return False

    natural_same_result_request = bool(
        re.search(
            r"\b(?:"
            r"(?:i\s+)?(?:need|want|would\s+like|can\s+i\s+(?:see|have))|"
            r"(?:show|give|display|draw|make|create|generate|render)(?:\s+me)?"
            r")\s+(?:an?\s*)?(?:chart|graph|plot|visualization)\s+"
            r"(?:of|for)\s+(?:it|that|this|those|these)\b",
            text,
            re.IGNORECASE,
        )
    )
    if natural_same_result_request:
        return True

    words = re.findall(r"[a-z]+", text.casefold())
    if not words or any(word not in _PRESENTATION_ONLY_TOKENS for word in words):
        return False

    presentation_action = bool(
        re.search(
            r"\b(?:show|make|draw|plot|graph|chart|visuali[sz]e|change|switch|"
            r"convert|redo|redraw|replot|restyle|use|turn)\b|"
            r"\b(?:as|into)\s+(?:a\s+)?(?:line|bar|area|scatter|pie|donut|doughnut)?"
            r"\s*(?:chart|graph|plot)\b",
            text,
            re.IGNORECASE,
        )
    )
    return presentation_action


def _normalize_chart_term_typos(text: str) -> str:
    """Normalize high-confidence presentation typos without fuzzy matching prose."""

    def replacement(match: re.Match[str]) -> str:
        word = match.group(0).casefold()
        if word.startswith("vis"):
            return "visualization"
        if word in {"achart", "charth", "chartt"}:
            return "chart"
        if word == "aplot":
            return "plot"
        return "graph"

    return _CHART_TERM_TYPO_RE.sub(replacement, text)


def build_chart_spec(
    question: str,
    result: QueryResult,
    candidate: Mapping[str, Any] | None = None,
    *,
    inherited_intent: ChartIntent | None = None,
) -> ChartSpec | None:
    """Build a validated chart spec from the current returned rows.

    ``candidate`` may select ``type``, ``title``, ``x``, ``y`` and ``series``.
    Other keys are ignored.  Candidate field names are resolved against returned
    columns case-insensitively, while all plotted values come from ``result``.
    Incompatible or unusable candidates fall back to deterministic inference.
    """

    intent = detect_chart_intent(question)
    if intent is None and inherited_intent is not None and not chart_output_suppressed(question):
        intent = inherited_intent
    if intent is None:
        return None

    try:
        rows = list(result.rows or [])
        columns = _result_columns(result, rows)
    except Exception:
        return None
    if not rows or len(columns) < 2:
        return None

    profiles = {
        column: _profile_field(column, rows)
        for column in columns
    }
    plan = candidate if isinstance(candidate, Mapping) else {}
    fallback_notes: list[str] = []

    raw_candidate_type = plan.get("type")
    candidate_type = _normalise_candidate_type(raw_candidate_type)
    if raw_candidate_type and candidate_type is None:
        fallback_notes.append("The suggested chart type was unsupported.")
    desired_type = intent.requested_type or candidate_type

    candidate_x = _resolve_field(plan.get("x"), columns)
    if candidate_x is not None and not _is_usable_chart_field(candidate_x):
        return None
    if (
        candidate_x is not None
        and intent.trigger == "trend"
        and profiles[candidate_x].kind != "temporal"
    ):
        candidate_x = None
        fallback_notes.append("The suggested x field was not temporal; it was inferred.")
    if plan.get("x") and candidate_x is None:
        fallback_notes.append("The suggested x field was unavailable; it was inferred.")
    x = candidate_x or _infer_x_field(columns, profiles, desired_type)
    if x is None:
        return None

    candidate_y = _resolve_y_fields(plan.get("y"), columns, exclude={x})
    if any(not _is_usable_chart_field(name) for name in candidate_y):
        return None
    if plan.get("y") and not candidate_y:
        fallback_notes.append("The suggested y fields were unavailable; they were inferred.")
    candidate_y = tuple(
        name
        for name in candidate_y
        if profiles[name].kind == "quantitative"
        and _is_usable_chart_field(name)
    )
    if plan.get("y") and not candidate_y and not any(
        "y fields" in note for note in fallback_notes
    ):
        fallback_notes.append("The suggested y fields were non-numeric; they were inferred.")
    y = candidate_y or _infer_y_fields(columns, profiles, exclude={x})
    if not y:
        return None

    candidate_series = _resolve_field(plan.get("series"), columns)
    if candidate_series is not None and not _is_usable_chart_field(candidate_series):
        return None
    if candidate_series in {x, *y}:
        candidate_series = None
    if candidate_series is not None and (
        profiles[candidate_series].kind != "nominal"
        or not _is_usable_chart_field(candidate_series)
    ):
        candidate_series = None
    if plan.get("series") and candidate_series is None:
        fallback_notes.append("The suggested series field was unavailable or incompatible.")
    series = candidate_series
    if series is None and desired_type not in {"pie", "donut"}:
        series = _infer_series_field(
            columns,
            profiles,
            exclude={x, *y},
        )

    sorted_rows = [
        row for row in rows
        if _json_safe_value(_row_value(row, x)) is not None
    ]
    if not sorted_rows:
        return None
    x_kind = profiles[x].kind
    if intent.trigger == "trend" and x_kind != "temporal":
        return None
    if x_kind == "temporal":
        sorted_rows.sort(key=lambda row: _temporal_sort_key(_row_value(row, x), name=x))

    data = _materialize_data(sorted_rows, x=x, y=y, series=series)
    if (
        series is not None
        and desired_type not in {"pie", "donut"}
        and _has_duplicate_coordinates(data, x=x, y=y, series=series)
    ):
        grouping_fields = (
            series,
            *(
                column
                for column in columns
                if column not in {x, *y, series}
                and profiles[column].kind == "nominal"
                and profiles[column].distinct_count >= 2
                and _is_usable_chart_field(column)
            ),
        )
        if len(grouping_fields) > 1:
            series = _composite_series_name(grouping_fields, columns)
            data = _materialize_data(
                sorted_rows,
                x=x,
                y=y,
                series=series,
                series_fields=grouping_fields,
            )
            fallback_notes.append(
                "Multiple grouping fields were combined into one chart series."
            )
    if _useful_mark_count(data, x=x, y=y) < 2:
        return None

    default_type: ChartType = "line" if (
        x_kind == "temporal"
        and _has_distinct_usable_x(data, x=x, y=y, minimum=2)
    ) else "bar"
    selected_type = desired_type or default_type
    if not _is_compatible_type(
        selected_type,
        x=x,
        x_kind=x_kind,
        y=y,
        series=series,
        data=data,
    ):
        source = "Requested" if intent.requested_type else "Suggested"
        fallback_notes.append(
            f"{source} {selected_type} chart is incompatible with the returned fields or values; "
            f"using {default_type}."
        )
        selected_type = default_type

    # The inferred default should already be compatible.  Keep the public API
    # non-throwing if an unusual payload still violates its requirements.
    if not _is_compatible_type(
        selected_type,
        x=x,
        x_kind=x_kind,
        y=y,
        series=series,
        data=data,
    ):
        return None

    if intent.unsupported_type:
        fallback_notes.insert(
            0,
            f"Requested {intent.unsupported_type} charts are not supported; "
            f"showing a {selected_type} chart instead.",
        )

    title = _clean_title(plan.get("title")) or _default_title(x, y)
    return ChartSpec(
        type=selected_type,
        title=title,
        x=x,
        y=y,
        series=series,
        x_kind=x_kind,
        trigger=intent.trigger,
        requested_type=intent.requested_type,
        fallback_reason=" ".join(fallback_notes) or None,
        truncated=False,
        data=data,
    )


def _requested_type_from_question(text: str) -> ChartType | None:
    restyle = _ANAPHORIC_TYPE_RE.search(text)
    if restyle:
        return _normalise_candidate_type(restyle.group("type"))
    for chart_type, pattern in _USER_TYPE_PATTERNS:
        if pattern.search(text):
            return chart_type
    return None


def _unsupported_type_from_question(text: str) -> str | None:
    for chart_type, pattern in _UNSUPPORTED_TYPE_PATTERNS:
        if pattern.search(text):
            return chart_type
    return None


def _normalise_candidate_type(value: Any) -> ChartType | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[\s_-]+", " ", value.strip().lower())
    cleaned = re.sub(r"\s+(?:chart|graph|plot)$", "", cleaned).strip()
    aliases = {
        "line": "line",
        "time series": "line",
        "timeseries": "line",
        "bar": "bar",
        "column": "bar",
        "area": "area",
        "stacked area": "area",
        "scatter": "scatter",
        "scatterplot": "scatter",
        "scatter plot": "scatter",
        "pie": "pie",
        "donut": "donut",
        "doughnut": "donut",
        "ring": "donut",
    }
    normalised = aliases.get(cleaned)
    return normalised if normalised in ALLOWED_CHART_TYPES else None  # type: ignore[return-value]


def _result_columns(result: QueryResult, rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    columns: list[str] = []
    seen: set[str] = set()
    for raw_column in result.columns or []:
        column = str(raw_column)
        if column and column not in seen:
            columns.append(column)
            seen.add(column)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for raw_column in row:
            column = str(raw_column)
            if column and column not in seen:
                columns.append(column)
                seen.add(column)
    return tuple(columns)


def _resolve_field(value: Any, columns: Sequence[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    requested = value.strip()
    if requested in columns:
        return requested
    matches = [column for column in columns if column.casefold() == requested.casefold()]
    return matches[0] if len(matches) == 1 else None


def _resolve_y_fields(
    value: Any,
    columns: Sequence[str],
    *,
    exclude: set[str],
) -> tuple[str, ...]:
    values: Sequence[Any]
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = value
    else:
        return ()

    resolved: list[str] = []
    for item in values:
        field_name = _resolve_field(item, columns)
        if field_name and field_name not in exclude and field_name not in resolved:
            resolved.append(field_name)
    return tuple(resolved)


def _profile_field(name: str, rows: Sequence[Mapping[str, Any]]) -> _FieldProfile:
    values = [_row_value(row, name) for row in rows]
    non_null = [value for value in values if value is not None]
    numeric_count = sum(_finite_number(value) is not None for value in non_null)
    numeric_type_count = sum(_is_numeric_value(value) for value in non_null)
    temporal_count = sum(_temporal_parts(value, name=name) is not None for value in non_null)

    if non_null and temporal_count / len(non_null) >= 0.8:
        kind: XKind = "temporal"
    elif non_null and numeric_type_count / len(non_null) >= 0.8:
        kind = "quantitative"
    else:
        kind = "nominal"

    distinct_values = {
        _hashable_value(_json_safe_value(value))
        for value in non_null
    }
    return _FieldProfile(
        name=name,
        kind=kind,
        non_null_count=len(non_null),
        numeric_count=numeric_count,
        distinct_count=len(distinct_values),
    )


def _infer_x_field(
    columns: Sequence[str],
    profiles: Mapping[str, _FieldProfile],
    desired_type: ChartType | None,
) -> str | None:
    by_kind: dict[XKind, list[str]] = {"temporal": [], "quantitative": [], "nominal": []}
    for column in columns:
        profile = profiles[column]
        if profile.non_null_count >= 2:
            by_kind[profile.kind].append(column)

    if desired_type in {"pie", "donut"}:
        preference: tuple[XKind, ...] = ("nominal", "temporal", "quantitative")
    elif desired_type == "scatter":
        preference = ("quantitative", "temporal", "nominal")
    elif desired_type in {"line", "area"}:
        preference = ("temporal", "nominal", "quantitative")
    else:
        preference = ("temporal", "nominal", "quantitative")

    for kind in preference:
        candidates = [
            column
            for column in by_kind[kind]
            if _is_usable_chart_field(column)
        ]
        if not candidates:
            continue
        return candidates[0]
    return None


def _infer_y_fields(
    columns: Sequence[str],
    profiles: Mapping[str, _FieldProfile],
    *,
    exclude: set[str],
) -> tuple[str, ...]:
    numeric = [
        column
        for column in columns
        if column not in exclude
        and profiles[column].kind == "quantitative"
        and profiles[column].numeric_count > 0
        and _is_usable_chart_field(column)
    ]
    return tuple(numeric)


def _infer_series_field(
    columns: Sequence[str],
    profiles: Mapping[str, _FieldProfile],
    *,
    exclude: set[str],
) -> str | None:
    for column in columns:
        if column in exclude:
            continue
        profile = profiles[column]
        if (
            _is_usable_chart_field(column)
            and profile.kind == "nominal"
            and profile.distinct_count >= 2
        ):
            return column
    return None


def _row_value(row: Mapping[str, Any], column: str) -> Any:
    if not isinstance(row, Mapping):
        return None
    if column in row:
        return row[column]
    matches = [key for key in row if str(key).casefold() == column.casefold()]
    return row[matches[0]] if len(matches) == 1 else None


def _materialize_data(
    rows: Sequence[Mapping[str, Any]],
    *,
    x: str,
    y: tuple[str, ...],
    series: str | None,
    series_fields: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {x: _json_safe_value(_row_value(row, x))}
        if series is not None:
            if series_fields:
                item[series] = " · ".join(
                    _series_value_label(_row_value(row, field_name))
                    for field_name in series_fields
                )
            else:
                item[series] = _json_safe_value(_row_value(row, series))
        for field_name in y:
            item[field_name] = _finite_number(_row_value(row, field_name))
        data.append(item)
    return data


def _composite_series_name(
    fields: Sequence[str],
    columns: Sequence[str],
) -> str:
    """Create a collision-free display field for multiple grouping dimensions."""

    base = " / ".join(fields)
    candidate = base
    suffix = 2
    while candidate in columns:
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def _series_value_label(value: Any) -> str:
    safe_value = _json_safe_value(value)
    if safe_value is None:
        return "Unknown"
    return str(safe_value)


def _useful_mark_count(data: Sequence[Mapping[str, Any]], *, x: str, y: Sequence[str]) -> int:
    return sum(
        1
        for row in data
        if row.get(x) is not None
        for field_name in y
        if _finite_number(row.get(field_name)) is not None
    )


def _is_compatible_type(
    chart_type: str,
    *,
    x: str,
    x_kind: XKind,
    y: tuple[str, ...],
    series: str | None,
    data: Sequence[Mapping[str, Any]],
) -> bool:
    if chart_type not in ALLOWED_CHART_TYPES or not y:
        return False
    if chart_type in {"line", "area"}:
        return (
            x_kind in {"temporal", "quantitative"}
            and _has_distinct_usable_x(data, x=x, y=y, minimum=2)
            and not _has_duplicate_coordinates(data, x=x, y=y, series=series)
        )
    if chart_type == "scatter":
        return (
            x_kind == "quantitative"
            and _has_distinct_usable_x(data, x=x, y=y, minimum=2)
        )
    if chart_type in {"pie", "donut"}:
        if x_kind != "nominal" or len(y) != 1 or series is not None:
            return False
        usable = [
            (_hashable_value(row.get(x)), _finite_number(row.get(y[0])))
            for row in data
            if row.get(x) is not None and _finite_number(row.get(y[0])) is not None
        ]
        values = [value for _, value in usable]
        categories = {category for category, _ in usable}
        return (
            len(values) >= 2
            and len(categories) >= 2
            and len(categories) == len(values)
            and all(value is not None and value >= 0 for value in values)
            and sum(value for value in values if value is not None) > 0
        )
    return chart_type == "bar" and not _has_duplicate_coordinates(
        data,
        x=x,
        y=y,
        series=series,
    )


def _has_duplicate_coordinates(
    data: Sequence[Mapping[str, Any]],
    *,
    x: str,
    y: Sequence[str],
    series: str | None,
) -> bool:
    seen: set[Any] = set()
    for row in data:
        if row.get(x) is None or not any(
            _finite_number(row.get(field_name)) is not None for field_name in y
        ):
            continue
        key = (
            _hashable_value(row.get(x)),
            _hashable_value(row.get(series)) if series is not None else None,
        )
        if key in seen:
            return True
        seen.add(key)
    return False


def _is_sensitive_identifier_field(name: str) -> bool:
    """Exclude row-level identifiers while allowing aggregate identifier metrics."""

    key = _identifier_key(name)
    if _ACCESS_METHOD_IDENTIFIER_RE.search(key):
        return True
    if _SAFE_PERIOD_ALIAS_RE.fullmatch(key):
        return False
    if _SAFE_ENTITY_AGGREGATE_RE.fullmatch(key):
        return False
    if (
        _BARE_ROW_IDENTIFIER_ALIAS_RE.fullmatch(key)
        or _NAMED_ROW_IDENTIFIER_ALIAS_RE.fullmatch(key)
    ):
        return True
    if not _IDENTIFIER_FIELD_RE.search(key):
        return False
    return _SAFE_IDENTIFIER_AGGREGATE_RE.fullmatch(key) is None


def _identifier_key(name: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_").casefold()


def _is_usable_chart_field(name: str) -> bool:
    return not _UNSAFE_RENDER_FIELD_RE.search(name) and not _is_sensitive_identifier_field(name)


def _has_distinct_usable_x(
    data: Sequence[Mapping[str, Any]],
    *,
    x: str,
    y: Sequence[str],
    minimum: int,
) -> bool:
    distinct = {
        _hashable_value(row.get(x))
        for row in data
        if row.get(x) is not None
        and any(_finite_number(row.get(field_name)) is not None for field_name in y)
    }
    return len(distinct) >= minimum


def _finite_number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        converted = float(value)
        return converted if math.isfinite(converted) else None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _is_numeric_value(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float, Decimal))


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return _finite_number(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _temporal_parts(value: Any, *, name: str = "") -> tuple[int, ...] | None:
    if isinstance(value, datetime):
        return (
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
        )
    if isinstance(value, date):
        return (value.year, value.month, value.day, 0, 0, 0, 0)
    period_unit = _period_unit_from_name(name)
    period_number = _integer_period_value(value)
    if period_unit is not None and period_number is not None:
        period_parts = _bounded_period_parts(period_unit, period_number)
        if period_parts is not None:
            return period_parts
    if (
        isinstance(value, int)
        and _TEMPORAL_FIELD_RE.search(name)
        and 1000 <= value <= 9999
    ):
        return (value, 1, 1, 0, 0, 0, 0)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if period_unit == "month":
        month_number = _MONTH_NUMBERS.get(text.casefold().rstrip("."))
        if month_number is not None:
            return _bounded_period_parts("month", month_number)
    if period_unit is not None and re.fullmatch(r"\d{1,4}", text):
        period_parts = _bounded_period_parts(period_unit, int(text))
        if period_parts is not None:
            return period_parts
    if period_unit == "quarter":
        short_quarter = re.fullmatch(r"(?:Q|Quarter\s*)([1-4])", text, re.IGNORECASE)
        if short_quarter:
            return _bounded_period_parts("quarter", int(short_quarter.group(1)))
    if period_unit == "week":
        short_week = re.fullmatch(r"(?:W|Week\s*)(\d{1,2})", text, re.IGNORECASE)
        if short_week:
            return _bounded_period_parts("week", int(short_week.group(1)))

    quarter = re.fullmatch(r"(\d{4})[\s-]*Q([1-4])", text, re.IGNORECASE)
    if quarter:
        return (int(quarter.group(1)), (int(quarter.group(2)) - 1) * 3 + 1, 1, 0, 0, 0, 0)
    week = re.fullmatch(r"(\d{4})[\s-]*W(\d{1,2})", text, re.IGNORECASE)
    if week:
        try:
            week_date = date.fromisocalendar(int(week.group(1)), int(week.group(2)), 1)
        except ValueError:
            return None
        return (week_date.year, week_date.month, week_date.day, 0, 0, 0, 0)
    year_month = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if year_month:
        year, month = int(year_month.group(1)), int(year_month.group(2))
        if 1 <= month <= 12:
            return (year, month, 1, 0, 0, 0, 0)
        return None
    if re.fullmatch(r"\d{4}", text) and _TEMPORAL_FIELD_RE.search(name):
        return (int(text), 1, 1, 0, 0, 0, 0)

    normalised = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed_datetime = datetime.fromisoformat(normalised)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None
        return (parsed_date.year, parsed_date.month, parsed_date.day, 0, 0, 0, 0)
    return (
        parsed_datetime.year,
        parsed_datetime.month,
        parsed_datetime.day,
        parsed_datetime.hour,
        parsed_datetime.minute,
        parsed_datetime.second,
        parsed_datetime.microsecond,
    )


def _period_unit_from_name(name: str) -> str | None:
    key = _identifier_key(name)
    for unit in ("month", "week", "quarter", "day", "year"):
        if re.search(
            rf"(?:^|_){unit}(?:_(?:num|number|name|of_year))?$",
            key,
            re.IGNORECASE,
        ):
            return unit
    return None


def _integer_period_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        finite = _finite_number(value)
        if finite is not None and float(finite).is_integer():
            return int(finite)
    return None


def _bounded_period_parts(unit: str, value: int) -> tuple[int, ...] | None:
    if unit == "year" and 1000 <= value <= 9999:
        return (value, 1, 1, 0, 0, 0, 0)
    if unit == "month" and 1 <= value <= 12:
        return (0, value, 1, 0, 0, 0, 0)
    if unit == "quarter" and 1 <= value <= 4:
        return (0, (value - 1) * 3 + 1, 1, 0, 0, 0, 0)
    if unit == "week" and 1 <= value <= 53:
        return (0, 1, value, 0, 0, 0, 0)
    if unit == "day" and 1 <= value <= 31:
        return (0, 1, value, 0, 0, 0, 0)
    return None


def _temporal_sort_key(value: Any, *, name: str = "") -> tuple[int, tuple[int, ...], str]:
    parts = _temporal_parts(value, name=name)
    if parts is not None:
        return (0, parts, "")
    if value is None:
        return (2, (), "")
    return (1, (), str(value).casefold())


def _hashable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable_value(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_hashable_value(item) for item in value)
    return value


def _clean_title(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(_CONTROL_RE.sub(" ", value).split())
    cleaned = _HTML_BRACKET_RE.sub("", cleaned).strip()
    return cleaned[:160].rstrip() or None


def _default_title(x: str, y: Sequence[str]) -> str:
    measures = [_humanize(field_name) for field_name in y[:2]]
    if len(y) > 2:
        measure_text = f"{measures[0]} and Other Measures"
    else:
        measure_text = " and ".join(measures)
    return f"{measure_text} by {_humanize(x)}"


def _humanize(field_name: str) -> str:
    words = re.sub(r"[_\-]+", " ", field_name).strip()
    return words.title() or "Metric"


__all__ = [
    "ALLOWED_CHART_TYPES",
    "ChartIntent",
    "ChartSpec",
    "build_chart_spec",
    "chart_output_suppressed",
    "detect_chart_intent",
    "is_anaphoric_chart_followup",
    "is_chart_only_followup",
]
