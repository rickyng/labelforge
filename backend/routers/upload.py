"""POST /api/upload — accept an order JSON file, create a session."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from ..dependencies import create_session
from ..schemas import UploadResponse
from ..utils import make_session_dir

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".json"}

_MAX_UPLOAD_BYTES = int(os.environ.get("LABELFORGE_MAX_UPLOAD_MB", "50")) * 1024 * 1024


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile) -> UploadResponse:
    """Upload an order JSON file. Returns a session_id for subsequent calls."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Only .json is accepted.",
        )

    tmp_dir = make_session_dir()
    input_path = tmp_dir / "input.json"

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(contents) // (1024*1024)} MB). Limit is {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    try:
        json.loads(contents)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {exc}") from exc

    input_path.write_bytes(contents)

    session = create_session(input_path=input_path, file_type="json", tmp_dir=tmp_dir)
    logger.info("Upload: filename=%s session=%s type=json size=%d", file.filename, session.session_id, len(contents))

    return UploadResponse(
        session_id=session.session_id,
        filename=file.filename,
        file_type="json",
        warning=None,
    )
