"""POST /api/upload — accept a PDF or .ai file, create a session."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from labelforge.utils import AI_COMPAT_WARNING, detect_file_type

from ..dependencies import create_session
from ..schemas import UploadResponse
from ..utils import make_session_dir

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".ai"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile) -> UploadResponse:
    """Upload a .pdf or .ai file. Returns a session_id for subsequent calls."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Only .pdf and .ai are accepted.",
        )

    tmp_dir = make_session_dir()
    input_path = tmp_dir / f"input{suffix}"

    contents = await file.read()
    input_path.write_bytes(contents)

    try:
        file_type = detect_file_type(input_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    session = create_session(input_path=input_path, file_type=file_type, tmp_dir=tmp_dir)

    warning = AI_COMPAT_WARNING if file_type == "ai" else None

    return UploadResponse(
        session_id=session.session_id,
        filename=file.filename,
        file_type=file_type,
        warning=warning,
    )
