"""POST /api/import-json/{session_id} — parse order JSON, build changes_data."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import fitz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from ..dependencies import require_role, SESSION_STORE
from ..schemas import ImportJsonResponse
from labelforge.changes_generator import build_changes, build_component_index, extract_fields
from labelforge.document_analyzer import extract_components

router = APIRouter()


@router.post("/import-json/{session_id}", response_model=ImportJsonResponse)
async def import_json(
    session_id: str,
    file: UploadFile = File(...),
    _role: str = Depends(require_role),
) -> ImportJsonResponse:
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    raw = await file.read()
    try:
        order = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}") from exc

    # Handle real Mango format: top-level is a list; styles under 'StyleColor', items under 'ItemData'
    if isinstance(order, list):
        order = order[0]

    styles = order.get("StyleColor") or order.get("Styles", [])
    if not styles:
        raise HTTPException(status_code=422, detail="No styles found in order JSON (expected 'StyleColor' or 'Styles').")

    style = styles[0]
    style_id = style.get("StyleID", "")
    color_code = style.get("MangoColorCode") or style.get("ColorCode", "")
    items = style.get("ItemData") or style.get("Items", [])
    if not items:
        raise HTTPException(status_code=422, detail="Style has no items (expected 'ItemData' or 'Items').")

    doc = fitz.open(str(session.input_path))
    try:
        components = extract_components(doc)
    finally:
        doc.close()
    index = build_component_index(components)

    sizes_out = []
    for item in items:
        size_name = item.get("SizeName", "")
        changes = build_changes(style, item, order, index)
        fields = extract_fields(style, item, order)
        sizes_out.append({"size_name": size_name, "changes": changes, "fields": fields})

    changes_data = {
        "source_file": file.filename or "order.json",
        "style_id": style_id,
        "color_code": color_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sizes": sizes_out,
    }
    session.extra["changes_data"] = changes_data
    session.extra["input_json_raw"] = raw.decode("utf-8", errors="replace")

    # DocumentComponent text IDs are "p{N}_t_b{B}_l{L}_s{S}"
    # but Label IDs from analyzer.py are "p{N}_b{B}_l{L}_s{S}" (no _t_ segment).
    # Remap so the frontend can match by label ID.
    def _to_label_id(cid: str) -> str:
        return cid.replace("_t_b", "_b")

    changes_by_size = {
        s["size_name"]: {_to_label_id(k): v for k, v in s["changes"].items()}
        for s in sizes_out
    }
    fields_by_size = {s["size_name"]: s["fields"] for s in sizes_out}
    return ImportJsonResponse(
        session_id=session_id,
        source_file=changes_data["source_file"],
        style_id=style_id,
        color_code=color_code,
        sizes=[s["size_name"] for s in sizes_out],
        changes_by_size=changes_by_size,
        fields_by_size=fields_by_size,
    )
