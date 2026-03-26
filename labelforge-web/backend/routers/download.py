"""GET /api/preview/{sid} and GET /api/download/{sid} — file streaming."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from ..dependencies import SessionData, get_session

router = APIRouter()


@router.get("/preview/{session_id}")
def preview_file(session_id: str) -> FileResponse:
    """Stream the original uploaded file as application/pdf for PDF.js."""
    session: SessionData = get_session(session_id)
    path = session.input_path
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input file not found.")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/download/{session_id}")
def download_file(session_id: str) -> FileResponse:
    """Stream the processed output file for download."""
    session: SessionData = get_session(session_id)
    if session.output_path is None or not session.output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found. Run /api/apply first.",
        )
    path = session.output_path
    media_type = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=f"labelforge_output{path.suffix}",
        headers={"Content-Disposition": f'attachment; filename="labelforge_output{path.suffix}"'},
    )
