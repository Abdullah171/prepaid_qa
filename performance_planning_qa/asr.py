"""Client helpers for the internal speech-to-text service."""

from __future__ import annotations

from typing import Any

import requests

from performance_planning_qa.config import ASRSettings


# Match the known-working standalone ASR script: do not route this internal
# corporate endpoint through an HTTP(S) proxy.
NO_PROXY: dict[str, str | None] = {"http": None, "https": None}


class ASRError(RuntimeError):
    """Base class for errors safe to expose through the API."""


class ASRConfigurationError(ASRError):
    pass


class ASRTimeoutError(ASRError):
    pass


class ASRUpstreamError(ASRError):
    pass


def is_wav(audio: bytes) -> bool:
    """Return whether *audio* has a standard RIFF/WAVE header."""

    return len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"


def transcribe_wav(audio: bytes, settings: ASRSettings) -> str:
    """Send one complete WAV recording to ASR and return its plain text."""

    try:
        settings.validate()
    except ValueError as exc:
        raise ASRConfigurationError(str(exc)) from exc

    try:
        response = requests.post(
            settings.transcribe_url,
            files={"audio": ("recording.wav", audio, "audio/wav")},
            verify=settings.verify_ssl,
            timeout=settings.timeout_seconds,
            proxies=NO_PROXY,
        )
    except requests.exceptions.Timeout as exc:
        raise ASRTimeoutError(
            f"ASR transcription timed out after {settings.timeout_seconds:g} seconds"
        ) from exc
    except requests.RequestException as exc:
        raise ASRUpstreamError(f"Could not reach the ASR service: {exc}") from exc

    if response.status_code != 200:
        detail = " ".join(response.text.split())[:300]
        suffix = f": {detail}" if detail else ""
        raise ASRUpstreamError(
            f"ASR service returned HTTP {response.status_code}{suffix}"
        )

    text = _transcription_text(response)
    if not text:
        raise ASRUpstreamError("ASR service returned an empty transcription")
    return text


def _transcription_text(response: requests.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    if isinstance(payload, dict):
        for field in ("text", "transcription", "transcript"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    if isinstance(payload, str):
        return payload.strip()
    return str(payload).strip() if payload is not None else ""
