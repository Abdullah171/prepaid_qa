"""Start the FastAPI backend and Streamlit frontend together.

The existing entry points remain independent; this file only supervises them.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_API_PORT = 8000
DEFAULT_STREAMLIT_PORT = 8501


def _available_port(preferred_port: int) -> int:
    """Return the preferred port, or the next available local port."""
    for port in range(preferred_port, preferred_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise RuntimeError(
        f"No available port found between {preferred_port} and {preferred_port + 99}."
    )


def _service_commands(api_port: int, streamlit_port: int) -> dict[str, list[str]]:
    return {
        "FastAPI": [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(api_port),
        ],
        "Streamlit": [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "frontend/app.py",
            "--server.port",
            str(streamlit_port),
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ],
    }


def _workbench_url(port: int) -> str | None:
    """Return Posit Workbench's session-proxied URL when running in Workbench."""
    if not os.getenv("RS_SERVER_URL"):
        return None

    candidates = [
        shutil.which("rserver-url"),
        "/usr/lib/rstudio-server/bin/rserver-url",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        result = subprocess.run(
            [candidate, "-l", str(port)],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def _start(command: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {"cwd": PROJECT_ROOT, "env": env}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def main() -> int:
    processes: dict[str, subprocess.Popen[bytes]] = {}

    try:
        api_port = _available_port(DEFAULT_API_PORT)
        streamlit_port = _available_port(DEFAULT_STREAMLIT_PORT)
        commands = _service_commands(api_port, streamlit_port)

        if api_port != DEFAULT_API_PORT:
            print(f"Port {DEFAULT_API_PORT} is busy; using {api_port} for FastAPI.")
        if streamlit_port != DEFAULT_STREAMLIT_PORT:
            print(
                f"Port {DEFAULT_STREAMLIT_PORT} is busy; "
                f"using {streamlit_port} for Streamlit."
            )

        env = os.environ.copy()
        env["PPQA_API_BASE_URL"] = f"http://127.0.0.1:{api_port}"
        env.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")
        for name, command in commands.items():
            processes[name] = _start(command, env)

        print(f"FastAPI:   http://127.0.0.1:{api_port} (docs: /docs)")
        workbench_url = _workbench_url(streamlit_port)
        if workbench_url:
            print(f"Streamlit (Posit Workbench): {workbench_url}")
            print(
                "For Posit Connect, deploy posit_app.py as a Streamlit app; "
                "publishing this notebook would create a notebook document instead."
            )
        else:
            print(f"Streamlit: http://127.0.0.1:{streamlit_port}")
        print("Press Ctrl+C to stop both services.", flush=True)

        while True:
            for name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    print(f"{name} stopped unexpectedly (exit code {return_code}).")
                    return return_code or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping both services...")
        return 0
    finally:
        for process in processes.values():
            _stop(process)


if __name__ == "__main__":
    raise SystemExit(main())
