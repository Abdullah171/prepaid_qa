"""Posit Connect entrypoint for the combined Streamlit and FastAPI app.

Posit Connect owns the Streamlit server and its public URL. Streamlit calls the
FastAPI application in-process so the deployment does not open a second port.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

# Set this before importing the frontend so every Streamlit session uses the
# FastAPI application in the same Posit Connect worker.
os.environ["PPQA_API_BASE_URL"] = "inprocess://ppqa"

from frontend.app import main  # noqa: E402


main()
