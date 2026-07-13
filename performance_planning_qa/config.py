"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


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
        env_prefix = {"glm": "GLM", "minmax": "MINIMAX"}.get(
            self.provider, self.provider.upper()
        )
        missing = []
        if not self.endpoint:
            missing.append(f"{env_prefix}_ENDPOINT")
        if not self.model:
            missing.append(f"{env_prefix}_MODEL")
        if not self.api_key:
            missing.append(f"{env_prefix}_API_KEY")
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
class ASRSettings:
    endpoint: str
    verify_ssl: bool
    timeout_seconds: float
    max_audio_bytes: int

    @property
    def transcribe_url(self) -> str:
        endpoint = self.endpoint.rstrip("/")
        if endpoint.endswith("/transcribe"):
            return endpoint
        return f"{endpoint}/transcribe"

    def validate(self) -> None:
        if not self.endpoint:
            raise ValueError("Missing ASR configuration: ASR_ENDPOINT")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ASR_ENDPOINT must be an absolute HTTP(S) URL")
        if self.timeout_seconds <= 0:
            raise ValueError("ASR_TIMEOUT_SECONDS must be greater than zero")
        if self.max_audio_bytes <= 0:
            raise ValueError("ASR_MAX_AUDIO_BYTES must be greater than zero")


@dataclass(frozen=True)
class ChatStorageSettings:
    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str
    schema_path: Path

    def validate(self) -> None:
        missing = []
        if not self.host:
            missing.append("CHAT_DB_HOST or Host")
        if not self.database:
            missing.append("CHAT_DB_NAME or Database")
        if not self.username:
            missing.append("CHAT_DB_USER or Username")
        if not self.password:
            missing.append("CHAT_DB_PASSWORD or Password")
        if missing:
            raise ValueError(f"Missing chat storage configuration: {', '.join(missing)}")
        if not self.schema_path.exists():
            raise ValueError(f"Chat memory schema file does not exist: {self.schema_path}")


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    schema_path: Path
    sample_data_dir: Path
    llm: LLMSettings
    asr: ASRSettings
    teradata: TeradataSettings
    chat_storage: ChatStorageSettings
    sql_repair_attempts: int
    prompt_log: PromptLogSettings


def load_settings(env_path: Path | None = None) -> AppSettings:
    load_environment(env_path)

    root = PROJECT_ROOT
    schema_path = Path(_get_any("SCHEMA_PATH", default=str(root / "performance.sql")) or "")
    sample_dir = Path(_get_any("SAMPLE_DATA_DIR", default=str(root / "sample_data")) or "")

    llm_provider = (_get_any("LLM_PROVIDER", default="glm") or "").lower()
    if llm_provider not in {"glm", "minmax"}:
        raise ValueError("LLM_PROVIDER must be either 'glm' or 'minmax'")
    llm_prefix = {"glm": "GLM", "minmax": "MINIMAX"}[llm_provider]

    llm = LLMSettings(
        provider=llm_provider,
        endpoint=_get_any(f"{llm_prefix}_ENDPOINT", default="") or "",
        model=_get_any(f"{llm_prefix}_MODEL", default="") or "",
        api_key=_get_any(f"{llm_prefix}_API_KEY", default="") or "",
        verify_ssl=_get_bool("LLM_VERIFY_SSL", default=False),
        timeout_seconds=_get_float("LLM_TIMEOUT_SECONDS", default=120.0),
        sql_temperature=_get_float("NL2SQL_TEMPERATURE", default=0.0),
        answer_temperature=_get_float("ANSWER_TEMPERATURE", default=0.2),
        max_tokens=_get_int("LLM_MAX_TOKENS", default=8096),
    )

    asr = ASRSettings(
        endpoint=_get_any("ASR_ENDPOINT", default="") or "",
        verify_ssl=_get_bool("ASR_VERIFY_SSL", default=False),
        timeout_seconds=_get_float("ASR_TIMEOUT_SECONDS", default=120.0),
        max_audio_bytes=_get_int("ASR_MAX_AUDIO_BYTES", default=25 * 1024 * 1024),
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

    chat_schema_path = Path(
        _get_any("CHAT_DB_SCHEMA_PATH", default=str(root / "sql" / "chat_memory_schema.sql")) or ""
    )
    if not chat_schema_path.is_absolute():
        chat_schema_path = root / chat_schema_path

    chat_storage = ChatStorageSettings(
        host=_get_any("CHAT_DB_HOST", "POSTGRES_HOST", "PGHOST", "Host", default="localhost")
        or "",
        port=_get_int(_first_existing_env("CHAT_DB_PORT", "POSTGRES_PORT", "PGPORT", "Port"), 5432),
        database=_get_any("CHAT_DB_NAME", "POSTGRES_DB", "PGDATABASE", "Database", default="")
        or "",
        username=_get_any("CHAT_DB_USER", "POSTGRES_USER", "PGUSER", "Username", default="")
        or "",
        password=_get_any("CHAT_DB_PASSWORD", "POSTGRES_PASSWORD", "PGPASSWORD", "Password", default="")
        or "",
        sslmode=_get_any("CHAT_DB_SSLMODE", "PGSSLMODE", default="disable") or "disable",
        schema_path=chat_schema_path,
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
        asr=asr,
        teradata=teradata,
        chat_storage=chat_storage,
        sql_repair_attempts=_get_int("SQL_REPAIR_ATTEMPTS", default=1),
        prompt_log=PromptLogSettings(
            enabled=_get_bool("LLM_PROMPT_LOG_ENABLED", default=False),
            directory=prompt_log_dir,
        ),
    )


def _first_existing_env(*names: str) -> str:
    for name in names:
        if os.getenv(name) is not None:
            return name
    return names[0]
