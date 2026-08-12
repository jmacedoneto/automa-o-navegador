"""Endpoint: POST /api/automation/import-trace

Accepts a Playwright trace JSON file (multipart upload), runs the recorder
heuristics, returns a steps.json draft for the user to review in the painel.
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.automation.recorder import NavRecorderError, parse_trace_file, steps_from_trace


router = APIRouter()


@router.post("/automation/import-trace")
async def import_trace(trace_file: UploadFile = File(...)) -> dict:
    """Accept a Playwright trace and return a NavRunner steps.json draft."""
    content = await trace_file.read()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        try:
            payload = parse_trace_file(tmp_path)
        except NavRecorderError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return steps_from_trace(payload)
    finally:
        tmp_path.unlink(missing_ok=True)