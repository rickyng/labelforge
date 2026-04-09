"""Endpoint for saving which labels are editable (admin only)."""

from __future__ import annotations

import json
from fastapi import APIRouter
from pydantic import BaseModel

from ..db import save_config
from ..dependencies import EDITABLE_CONFIG, get_session

router = APIRouter()


class EditableConfig(BaseModel):
    editable_ids: list[str]
    name: str


@router.post("/editable/{session_id}")
async def save_editable(
    session_id: str,
    body: EditableConfig,
) -> dict[str, int]:
    """Persist which label IDs are editable, keyed by the session's input filename."""
    import fitz
    from labelforge.document_analyzer import extract_components

    session = get_session(session_id)
    filename = session.input_path.name
    # Update in-memory cache
    EDITABLE_CONFIG[filename] = body.editable_ids

    # Get components from session cache or re-extract
    components = session.extra.get("components")
    if components is None:
        doc = fitz.open(str(session.input_path))
        try:
            components = extract_components(doc)
        finally:
            doc.close()

    # Derive labels_data from TEXT components
    labels_data = [
        {
            "id": c.id,
            "page": c.page,
            "bbox": list(c.bbox),
            "original_text": c.text or "",
            "new_text": None,
            "fontname": c.fontname or "helv",
            "fontsize": c.fontsize or 10,
            "color": c.color or "#000000",
            "flags": 0,
            "rotation": 0,
            "origin": None,
            "auto_fit": True,
            "max_scale_down": 0.5,
            "padding": 0,
            "white_out": False,
        }
        for c in components
        if c.type == "TEXT"
    ]

    # Get page_count
    doc = fitz.open(str(session.input_path))
    page_count = doc.page_count
    doc.close()

    # Persist to DB with full data
    file_blob = session.input_path.read_bytes()
    changes_data = session.extra.get("changes_data")
    input_json_raw = session.extra.get("input_json_raw")
    changes_json = json.dumps(changes_data) if changes_data is not None else None
    mapping_name = session.extra.get("mapping_name")

    save_config(
        name=body.name,
        filename=filename,
        labels=labels_data,
        editable_ids=body.editable_ids,
        file_blob=file_blob,
        page_count=page_count,
        file_type=session.file_type,
        input_json=input_json_raw,
        changes_json=changes_json,
        mapping_name=mapping_name,
    )
    return {"saved": len(body.editable_ids)}
