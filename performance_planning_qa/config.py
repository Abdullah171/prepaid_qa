"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment(env_path: Path | None = None) -> None:
    """Load .env values without overriding already-exported variables."""

    env_file = env_path or PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_fallback(env_file)
        return

    load_dotenv(dotenv_path=env_file, override=False)


def _load_env_fallback(env_file: Path) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _get_any(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value.strip().strip('"').strip("'")
    return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got {raw!r}") from exc


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    endpoint: str
    model: str
    api_key: str
    verify_ssl: bool
    timeout_seconds: float
    sql_temperature: float
    answer_temperature: float
    max_tokens: int

    @property
    def base_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        suffix = "/chat/completions"
        if endpoint.endswith(suffix):
            endpoint = endpoint[: -len(suffix)]
        return endpoint

    def validate(self) -> None:
        missing = []
        if not self.endpoint:
            missing.append("STC_MINIMAX_ENDPOINT")
        if not self.model:
            missing.append("DEFAULT_STC_MINIMAX_MODEL")
        if missing:
            raise ValueError(f"Missing LLM configuration: {', '.join(missing)}")


@dataclass(frozen=True)
class TeradataSettings:
    host: str
    username: str
    password: str
    database: str | None
    logmech: str | None
    logdata: str | None
    temp_database_name: str | None

    def validate(self) -> None:
        missing = []
        if not self.host:
            missing.append("TERADATA_HOST_NAME")
        if not self.username:
            missing.append("TERADATA_USER")
        if not self.password:
            missing.append("TERADATA_PASSWORD")
        if missing:
            raise ValueError(f"Missing Teradata configuration: {', '.join(missing)}")


@dataclass(frozen=True)
class PromptLogSettings:
    enabled: bool
    directory: Path


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    schema_path: Path
    sample_data_dir: Path
    llm: LLMSettings
    teradata: TeradataSettings
    query_max_rows: int
    answer_result_max_chars: int
    sql_repair_attempts: int
    prompt_log: PromptLogSettings


def load_settings(env_path: Path | None = None) -> AppSettings:
    load_environment(env_path)

    root = PROJECT_ROOT
    schema_path = Path(_get_any("SCHEMA_PATH", default=str(root / "performance.sql")) or "")
    sample_dir = Path(_get_any("SAMPLE_DATA_DIR", default=str(root / "sample_data")) or "")

    llm = LLMSettings(
        provider=_get_any("ANALYSIS_PROVIDER", default="stc/minimax2.7") or "",
        endpoint=_get_any("STC_MINIMAX_ENDPOINT", "MINIMAX_ENDPOINT", default="") or "",
        model=_get_any("DEFAULT_STC_MINIMAX_MODEL", "STC_MINIMAX_MODEL", default="") or "",
        api_key=_get_any("STC_MINIMAX_API_KEY", "MINIMAX_API_KEY", default="not-needed") or "not-needed",
        verify_ssl=_get_bool("STC_MINIMAX_VERIFY_SSL", default=False),
        timeout_seconds=_get_float("STC_MINIMAX_TIMEOUT_SECONDS", default=120.0),
        sql_temperature=_get_float("NL2SQL_TEMPERATURE", default=0.0),
        answer_temperature=_get_float("ANSWER_TEMPERATURE", default=0.2),
        max_tokens=_get_int("STC_MINIMAX_MAX_TOKENS", default=20000),
    )

    teradata = TeradataSettings(
        host=_get_any("TERADATA_HOST_NAME", "TERADATA_HOST", "TD_HOST", default="") or "",
        username=_get_any("TERADATA_USER", "TERADATA_USERNAME", "TD_USER", default="") or "",
        password=_get_any("TERADATA_PASSWORD", "TERADATA_PASS", "TD_PASSWORD", default="") or "",
        database=_get_any("TERADATA_DATABASE", "TD_DATABASE"),
        logmech=_get_any("TERADATA_LOGMECH", "TD_LOGMECH"),
        logdata=_get_any("TERADATA_LOGDATA", "TD_LOGDATA"),
        temp_database_name=_get_any("TERADATA_TEMP_DATABASE", "TERADATA_TEMP_DATABASE_NAME"),
    )

    prompt_log_dir = Path(
        _get_any("LLM_PROMPT_LOG_DIR", default=str(root / "logs" / "llm_prompts")) or ""
    )
    if not prompt_log_dir.is_absolute():
        prompt_log_dir = root / prompt_log_dir

    return AppSettings(
        project_root=root,
        schema_path=schema_path,
        sample_data_dir=sample_dir,
        llm=llm,
        teradata=teradata,
        query_max_rows=_get_int("QUERY_MAX_ROWS", default=200),
        answer_result_max_chars=_get_int("ANSWER_RESULT_MAX_CHARS", default=60000),
        sql_repair_attempts=_get_int("SQL_REPAIR_ATTEMPTS", default=1),
        prompt_log=PromptLogSettings(
            enabled=_get_bool("LLM_PROMPT_LOG_ENABLED", default=False),
            directory=prompt_log_dir,
        ),
    )
