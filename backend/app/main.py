"""Shim that re-exports the FastAPI app instance.

The real application is constructed in `backend/main.py` (the Docker
entrypoint is `uvicorn main:app`). This module exists so tests and
internal callers can do `from app.main import app` regardless of where
they were launched from.
"""
from main import app  # noqa: F401  (re-export)