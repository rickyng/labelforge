"""GET /api/preview/{sid} and GET /api/download/{sid} — file streaming."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from ..dependencies import SessionData, get_session

logger = logging.getLogger(__name__)

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


@router.get("/preview-images/{session_id}")
def list_preview_images(session_id: str) -> JSONResponse:
    """Return URLs for rasterized PNG pages (for .ai file preview)."""
    session: SessionData = get_session(session_id)
    if not session.preview_images:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No preview images available.")
    pages = [
        {"page": p, "url": f"/api/preview-image/{session_id}/{p}"}
        for p in sorted(session.preview_images)
    ]
    # Include page dimensions in PDF points for overlay scaling
    import fitz
    doc = fitz.open(str(session.input_path))
    first_page = doc[0]
    page_width = first_page.rect.width
    page_height = first_page.rect.height
    doc.close()
    return JSONResponse({"pages": pages, "dpi": 150, "page_width": page_width, "page_height": page_height})


@router.get("/preview-image/{session_id}/{page:int}")
def serve_preview_image(session_id: str, page: int) -> FileResponse:
    """Serve a single rasterized PNG page."""
    session: SessionData = get_session(session_id)
    path = session.preview_images.get(page)
    if path is None or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview image not found.")
    return FileResponse(
        path=str(path),
        media_type="image/png",
        filename=f"page_{page}.png",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/output-preview/{session_id}")
def output_preview_file(session_id: str) -> FileResponse:
    """Stream the current output file (after apply/barcode replace) for preview."""
    session: SessionData = get_session(session_id)
    path = (
        session.output_path
        if session.output_path and session.output_path.exists()
        else session.input_path
    )
    if not path or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
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
    logger.info("Download: session=%s file=%s", session_id, path.name)
    media_type = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=f"labelforge_output{path.suffix}",
        headers={"Content-Disposition": f'attachment; filename="labelforge_output{path.suffix}"'},
    )
