"""Start the FastAPI backend and Streamlit frontend together.

The existing entry points remain independent; this file only supervises them.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

SERVICES = {
    "FastAPI": [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ],
    "Streamlit": [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "frontend/app.py",
        "--server.port",
        "8501",
    ],
}


def _start(command: list[str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {"cwd": PROJECT_ROOT}
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
        for name, command in SERVICES.items():
            processes[name] = _start(command)

        print("FastAPI:   http://127.0.0.1:8000 (docs: /docs)")
        print("Streamlit: http://127.0.0.1:8501")
        print("Press Ctrl+C to stop both services.")

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
