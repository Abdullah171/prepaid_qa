"""Posit Connect entrypoint for the combined Streamlit and FastAPI app.

Posit Connect owns the public Streamlit server and its URL. The FastAPI service
is intentionally started on a private loopback port inside the same worker.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from performance_planning_qa.embedded_api import get_embedded_api_url


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

# Set this before importing the frontend so every Streamlit session uses the
# private API belonging to its Posit Connect worker.
os.environ["PPQA_API_BASE_URL"] = get_embedded_api_url()

from frontend.app import main  # noqa: E402


main()
