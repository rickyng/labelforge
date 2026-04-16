"""Component extraction endpoint.

POST /api/components/{session_id} — extract all document components
"""

from __future__ import annotations

import logging

import fitz
from fastapi import APIRouter

from labelforge.component_models import DocumentComponent
from labelforge.document_analyzer import extract_components

from ..dependencies import get_session, SessionData
from ..schemas import ComponentDTO, ComponentsResponse

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
        fill_color=c.fill_color,
        fill_opacity=c.fill_opacity,
        stroke_color=c.stroke_color,
        stroke_width=c.stroke_width,
        ocr_text=c.ocr_text,
        ocr_confidence=c.ocr_confidence,
        ocr_language=c.ocr_language,
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
