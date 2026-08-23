"""Cloudera Machine Learning launcher for Prepaid QA.

Create the CML application with this file as its launch script. Configure the
``REPLACE_ME`` values below, or provide them as CML project environment
variables. CML injects ``CDSW_APP_PORT`` automatically.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping


_SCRIPT_FILE = globals().get("__file__")
PROJECT_ROOT = (
    Path(_SCRIPT_FILE).resolve().parent
    if _SCRIPT_FILE
    else Path.cwd().resolve()
)

# These values are deployment defaults. Existing CML project environment
# variables take precedence, which keeps credentials out of source control.
CML_ENV = {
    # LLM provider
    "LLM_PROVIDER": "glm",
    "GLM_ENDPOINT": "https://litellm.apps.coherecls02.stc.corp/chat/completions",
    "GLM_MODEL": "GLM-5.2",
    "GLM_API_KEY": "sk-H2PyHg9YjjX4B5LuMUnIoQ",
    "GLM_STREAM": "true",
    "GLM_TIMEOUT_SECONDS": "1800",
    "GLM_MAX_RETRIES": "2",
    "GLM_RETRY_BACKOFF_SECONDS": "2",
    "LLM_VERIFY_SSL": "false",

    # Teradata (use a SELECT-only account)
    "TERADATA_HOST_NAME": "172.21.237.135",
    "TERADATA_USER": "AP_CVMBIGDATA",
    "TERADATA_PASSWORD": "G15c6n19$",

    # Schema, sample context, and chat history
    "SCHEMA_PATH": "prepaid.sql",
    "SAMPLE_DATA_DIR": "sample_data",
    "chat_db": "duckdb",
    "CHAT_DUCKDB_PATH": "data/chat_history.duckdb",
    "CHAT_DB_DUCKDB_SCHEMA_PATH": "sql/chat_memory_schema_duckdb.sql",
    "CHAT_TERADATA_DATABASE": "DP_EDW_PPF_STG",

    # Application behavior
    "SQL_REPAIR_ATTEMPTS": "1",
    "LLM_PROMPT_LOG_ENABLED": "false",
    "PPQA_ALLOW_API_URL_EDIT": "false",
    "PPQA_LOG_LEVEL": "INFO",
    "ARROW_DEFAULT_MEMORY_POOL": "system",
}


def _deployment_environment() -> dict[str, str]:
    """Combine the local/CML environment with the deployment defaults."""

    environment = os.environ.copy()
    # This also makes a bundled .env file usable, while never overriding
    # environment variables configured directly in CML.
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name:
                environment.setdefault(name, value)

    for name, value in CML_ENV.items():
        environment.setdefault(name, value)
    return environment


def _validate_configuration(environment: Mapping[str, str]) -> None:
    required = {
        "TERADATA_HOST_NAME": ("TERADATA_HOST_NAME", "TERADATA_HOST", "TD_HOST"),
        "TERADATA_USER": ("TERADATA_USER", "TERADATA_USERNAME", "TD_USER"),
        "TERADATA_PASSWORD": (
            "TERADATA_PASSWORD",
            "TERADATA_PASS",
            "TD_PASSWORD",
        ),
    }

    provider = environment.get("LLM_PROVIDER", "").strip().lower()
    if provider == "glm":
        required.update(
            {
                "GLM_ENDPOINT": ("GLM_ENDPOINT",),
                "GLM_API_KEY": ("GLM_API_KEY",),
                "GLM_MODEL": ("GLM_MODEL",),
            }
        )
    elif provider == "minmax":
        required.update(
            {
                "MINIMAX_ENDPOINT": ("MINIMAX_ENDPOINT",),
                "MINIMAX_API_KEY": ("MINIMAX_API_KEY",),
                "MINIMAX_MODEL": ("MINIMAX_MODEL",),
            }
        )
    else:
        raise RuntimeError("LLM_PROVIDER must be either 'glm' or 'minmax'.")

    chat_backend = environment.get("chat_db", environment.get("CHAT_DB", "local"))
    chat_backend = chat_backend.strip().lower()
    if chat_backend == "teradata":
        required["CHAT_TERADATA_DATABASE"] = ("CHAT_TERADATA_DATABASE",)
    elif chat_backend == "local":
        required.update(
            {
                "CHAT_DB_HOST": ("CHAT_DB_HOST", "POSTGRES_HOST", "PGHOST", "Host"),
                "CHAT_DB_NAME": ("CHAT_DB_NAME", "POSTGRES_DB", "PGDATABASE", "Database"),
                "CHAT_DB_USER": ("CHAT_DB_USER", "POSTGRES_USER", "PGUSER", "Username"),
                "CHAT_DB_PASSWORD": (
                    "CHAT_DB_PASSWORD",
                    "POSTGRES_PASSWORD",
                    "PGPASSWORD",
                    "Password",
                ),
            }
        )
    elif chat_backend != "duckdb":
        raise RuntimeError("chat_db must be 'local', 'teradata', or 'duckdb'.")

    unfinished = sorted(
        label
        for label, names in required.items()
        if not any(
            value and "REPLACE_ME" not in value
            for value in (environment.get(name, "").strip() for name in names)
        )
    )
    if unfinished:
        raise RuntimeError(
            "Configure these CML environment variables before deployment: "
            + ", ".join(unfinished)
        )

    for name in ("SCHEMA_PATH", "SAMPLE_DATA_DIR"):
        configured_path = Path(environment[name])
        path = (
            configured_path
            if configured_path.is_absolute()
            else PROJECT_ROOT / configured_path
        )
        if not path.exists():
            raise RuntimeError(f"{name} does not exist: {path}")

    if not (PROJECT_ROOT / "posit_app.py").is_file():
        raise RuntimeError(f"posit_app.py does not exist in {PROJECT_ROOT}")


def main() -> None:
    public_port = os.getenv("CDSW_APP_PORT", "").strip()
    if not public_port.isdigit():
        raise RuntimeError(
            "CDSW_APP_PORT is missing. Run cml_entry.py as a CML Application."
        )

    environment = _deployment_environment()
    _validate_configuration(environment)

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "posit_app.py"),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        public_port,
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    # CML runs application scripts through an IPython kernel. Keep that kernel
    # alive and run Streamlit as its child process.
    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
