"""Endpoint for saving which labels are editable (admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import save_config
from ..dependencies import EDITABLE_CONFIG, get_session, require_role

router = APIRouter()


class EditableConfig(BaseModel):
    editable_ids: list[str]
    name: str


@router.post("/editable/{session_id}")
async def save_editable(
    session_id: str,
    body: EditableConfig,
    _role: str = Depends(require_role),
) -> dict[str, int]:
    """Persist which label IDs are editable, keyed by the session's input filename."""
    from labelforge.applier import load_labels
    import fitz
    import json
    session = get_session(session_id)
    filename = session.input_path.name
    # Update in-memory cache
    EDITABLE_CONFIG[filename] = body.editable_ids
    # Persist to DB with full labels snapshot
    if session.labels_json_path and session.labels_json_path.exists():
        labels = load_labels(session.labels_json_path)
        doc = fitz.open(str(session.input_path))
        page_count = doc.page_count
        doc.close()
        labels_data = [
            {
                "id": lbl.id, "page": lbl.page, "bbox": list(lbl.bbox),
                "original_text": lbl.original_text, "new_text": lbl.new_text,
                "fontname": lbl.fontname, "fontsize": lbl.fontsize, "color": lbl.color,
                "flags": lbl.flags, "rotation": lbl.rotation,
                "origin": list(lbl.origin) if lbl.origin else None,
                "auto_fit": lbl.auto_fit, "max_scale_down": lbl.max_scale_down,
                "padding": lbl.padding, "white_out": lbl.white_out,
            }
            for lbl in labels
        ]
        file_blob = session.input_path.read_bytes()
        save_config(
            name=body.name,
            filename=filename,
            labels=labels_data,
            editable_ids=body.editable_ids,
            file_blob=file_blob,
            page_count=page_count,
            file_type=session.file_type,
        )
    return {"saved": len(body.editable_ids)}
