"""Component extraction and barcode replacement endpoints.

POST /api/components/{session_id}          — extract all document components
GET  /api/components/{session_id}/{cid}/thumbnail — return component thumbnail
POST /api/components/{session_id}/{cid}/replace-barcode — replace barcode image
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from labelforge.component_models import BarcodeFormat, DocumentComponent
from labelforge.document_analyzer import extract_components
from labelforge.barcode_handler import apply_barcode_replacement

from ..dependencies import get_session, SessionData
from ..schemas import ComponentDTO, ComponentsResponse, ReplaceBarcodeRequest, ReplaceBarcodeResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _component_to_dto(c: DocumentComponent) -> ComponentDTO:
    return ComponentDTO(
        id=c.id,
        type=c.type.value,
        page=c.page,
        bbox=list(c.bbox),
        xref=c.xref,
        text=c.text,
        fontname=c.fontname,
        fontsize=c.fontsize,
        color=c.color,
        image_format=c.image_format,
        width_px=c.width_px,
        height_px=c.height_px,
        thumbnail_b64=c.thumbnail_b64,
        barcode_value=c.barcode_value,
        barcode_format=c.barcode_format.value if c.barcode_format else None,
        editable=c.editable,
    )


@router.post("/components/{session_id}", response_model=ComponentsResponse)
def analyze_components(session_id: str) -> ComponentsResponse:
    """Extract all components (text, images, barcodes, shapes) from the uploaded file."""
    session: SessionData = get_session(session_id)

    doc = fitz.open(str(session.input_path))
    try:
        page_count = doc.page_count
        components = extract_components(doc)
    finally:
        doc.close()

    # Cache on session for later lookup
    session.extra["components"] = components

    dtos = [_component_to_dto(c) for c in components]
    logger.info("Session %s: extracted %d components", session_id, len(dtos))
    return ComponentsResponse(
        session_id=session_id,
        components=dtos,
        page_count=page_count,
    )


@router.get("/components/{session_id}/{component_id}/thumbnail")
def get_thumbnail(session_id: str, component_id: str) -> JSONResponse:
    """Return the base64 thumbnail for an image/barcode component."""
    session: SessionData = get_session(session_id)
    components: list[DocumentComponent] = session.extra.get("components", [])
    comp = next((c for c in components if c.id == component_id), None)
    if comp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    return JSONResponse({"thumbnail_b64": comp.thumbnail_b64})


@router.post("/components/{session_id}/{component_id}/replace-barcode", response_model=ReplaceBarcodeResponse)
def replace_barcode(
    session_id: str,
    component_id: str,
    body: ReplaceBarcodeRequest,
) -> ReplaceBarcodeResponse:
    """Generate a new barcode image and replace the original component in the PDF."""
    session: SessionData = get_session(session_id)
    components: list[DocumentComponent] = session.extra.get("components", [])

    comp = next((c for c in components if c.id == component_id), None)
    if comp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")

    try:
        fmt = BarcodeFormat(body.fmt)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown barcode format: {body.fmt}")

    size_px: tuple[int, int] | None = None
    if comp.width_px and comp.height_px:
        size_px = (comp.width_px, comp.height_px)
    else:
        # Vector barcode: derive pixel size from bbox dimensions (points → px at 150 DPI)
        w_pt = comp.bbox[2] - comp.bbox[0]
        h_pt = comp.bbox[3] - comp.bbox[1]
        if w_pt > 0 and h_pt > 0:
            dpi = 150
            size_px = (max(1, round(w_pt * dpi / 72)), max(1, round(h_pt * dpi / 72)))

    output_filename = f"barcode_output_{session_id[:8]}.pdf"
    output_path = session.tmp_dir / output_filename

    try:
        apply_barcode_replacement(
            input_path=session.working_path,
            output_path=output_path,
            page_num=comp.page,
            bbox=comp.bbox,
            value=body.value,
            fmt=fmt,
            size_px=size_px,
        )
    except Exception as exc:
        logger.exception("Barcode replacement failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    session.output_path = output_path
    return ReplaceBarcodeResponse(
        session_id=session_id,
        component_id=component_id,
        output_filename=output_filename,
    )
