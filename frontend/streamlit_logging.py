"""Targeted logging cleanup for benign Streamlit lifecycle races."""

from __future__ import annotations

import logging


_APP_SESSION_LOGGER = "streamlit.runtime.app_session"
_FILTER_MARKER = "_ppqa_stale_fragment_info_filter"
_STALE_FRAGMENT_PREFIX = "The fragment with id "
_STALE_FRAGMENT_SUFFIX = (
    " does not exist anymore - it might have been removed during a preceding "
    "full-app rerun."
)


class StaleFragmentInfoFilter(logging.Filter):
    """Hide only Streamlit's expected stale-fragment informational message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != _APP_SESSION_LOGGER or record.levelno != logging.INFO:
            return True

        message = record.getMessage()
        is_stale_fragment_message = message.startswith(
            _STALE_FRAGMENT_PREFIX
        ) and message.endswith(_STALE_FRAGMENT_SUFFIX)
        return not is_stale_fragment_message


def install_stale_fragment_info_filter() -> None:
    """Install the filter once, including across Streamlit script reruns."""

    app_session_logger = logging.getLogger(_APP_SESSION_LOGGER)
    if any(
        getattr(existing_filter, _FILTER_MARKER, False)
        for existing_filter in app_session_logger.filters
    ):
        return

    stale_fragment_filter = StaleFragmentInfoFilter()
    setattr(stale_fragment_filter, _FILTER_MARKER, True)
    app_session_logger.addFilter(stale_fragment_filter)
