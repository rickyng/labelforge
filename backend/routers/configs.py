"""CRUD endpoints for persisted editable configs."""

from __future__ import annotations

from pathlib import Path

import json as _json
import shutil
import fitz
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..apply_utils import apply_changes_to_pdf
from ..db import delete_config, get_config, list_configs, update_name
from ..dependencies import create_session, SessionData, rasterize_ai_preview, _text_components_to_label_dtos
from ..schemas import AnalyzeResponse, ComponentMapResponse, ConfigSummary, ProfileApplyResponse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter()


@router.get("/configs", response_model=list[ConfigSummary])
def list_all_configs() -> list[ConfigSummary]:
    """List all saved editable configs."""
    return [ConfigSummary(**row) for row in list_configs()]


@router.get("/configs/{name:path}/template-data", response_model=ComponentMapResponse)
def get_profile_template_data(
    name: str,
    template_name: str = Query(..., description="Label template name"),
) -> ComponentMapResponse:
    """Resolve a profile's stored order JSON against a template.

    Returns resolved fields and per-size component changes without applying.
    """
    from ..label_mapping import build_component_changes

    row = get_config(name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found.")

    raw_input_json = row.get("input_json")
    if not raw_input_json:
        raise HTTPException(
            status_code=422,
            detail="No order JSON stored for this profile. Re-save from Admin.",
        )
    order_data = _json.loads(raw_input_json)

    result = build_component_changes(template_name, order_data)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_name}' not found.",
        )

    return ComponentMapResponse(**result)


@router.get("/configs/{name:path}", response_model=AnalyzeResponse)
def load_config(
    name: str,
) -> AnalyzeResponse:
    """Load a config by profile name — creates a live session from the stored file blob."""
    row = get_config(name)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config '{name}' not found.")

    if not row.get("file_blob"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No file stored for this profile. Please re-save from the Labels tab.",
        )

    # Restore the file to a new temp session
    tmp_dir = make_session_dir()
    suffix = ".ai" if row["file_type"] == "ai" else ".pdf"
    input_path = tmp_dir / f"input{suffix}"
    input_path.write_bytes(row["file_blob"])

    # For .ai files, convert to clean PDF so PDF.js renders correctly
    ai_src_path = None
    if row["file_type"] == "ai":
        ai_doc = fitz.open(str(input_path))
        pdf_path = tmp_dir / "input.pdf"
        ai_doc.save(str(pdf_path))
        ai_doc.close()
        input_path = pdf_path
        # Keep .ai source for rasterization (after session creation)
        ai_src_path = tmp_dir / "input.ai"
        ai_src_path.write_bytes(row["file_blob"])

    session = create_session(input_path=input_path, file_type=row["file_type"], tmp_dir=tmp_dir)

    # Rasterize .ai pages for browser preview
    if ai_src_path:
        rasterize_ai_preview(session, ai_src_path)

    mapping_name = row.get("mapping_name")
    if mapping_name:
        session.extra["mapping_name"] = mapping_name

    # Extract components and cache on session (single source of truth)
    doc = fitz.open(str(input_path))
    components = extract_components(doc)
    doc.close()
    session.extra["components"] = components

    label_dtos = _text_components_to_label_dtos(components)

    raw_changes = row.get("changes_json", "{}")
    changes_data = _json.loads(raw_changes) if raw_changes and raw_changes != "{}" else None
    return AnalyzeResponse(
        session_id=session.session_id,
        labels=label_dtos,
        page_count=row["page_count"],
        file_type=row["file_type"],
        editable_ids=row["editable_ids"],
        changes_data=changes_data,
        warning=None,
        mapping_name=mapping_name,
    )


class RenameBody(BaseModel):
    name: str


@router.patch("/configs/{name:path}/name", status_code=status.HTTP_204_NO_CONTENT)
def rename_config(
    name: str,
    body: RenameBody,
) -> None:
    """Rename a profile."""
    if not update_name(name, body.name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config '{name}' not found.")


@router.delete("/configs/{name:path}", status_code=status.HTTP_204_NO_CONTENT)
def remove_config(
    name: str,
) -> None:
    """Delete a saved config entry."""
    if not delete_config(name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config '{name}' not found.")


@router.post("/configs/{name:path}/apply", response_model=ProfileApplyResponse)
def apply_profile(
    name: str,
    size_name: str = Query(..., description="Size variant, e.g. 'XS'"),
) -> ProfileApplyResponse:
    row = get_config(name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found.")
    if not row.get("file_blob"):
        raise HTTPException(status_code=422, detail="No file stored for this profile.")

    raw_changes = row.get("changes_json", "{}")
    changes_data = _json.loads(raw_changes) if raw_changes else {}
    sizes = changes_data.get("sizes", [])
    size_entry = next((s for s in sizes if s["size_name"] == size_name), None)
    if size_entry is None:
        available = [s["size_name"] for s in sizes]
        raise HTTPException(
            status_code=404,
            detail=f"Size '{size_name}' not found. Available: {available}",
        )
    changes = size_entry["changes"]

    tmp_dir = make_session_dir()
    suffix = ".ai" if row["file_type"] == "ai" else ".pdf"
    input_path = tmp_dir / f"input{suffix}"
    input_path.write_bytes(row["file_blob"])

    _, session, changed_count, warning_msg = _apply_changes_to_pdf(
        input_path, changes, file_type=row["file_type"],
    )

    output_filename = f"{name}_{size_name}.pdf"
    return ProfileApplyResponse(
        session_id=session.session_id,
        size_name=size_name,
        changed_count=changed_count,
        output_filename=output_filename,
        warning=warning_msg,
    )


@router.post("/configs/{name:path}/apply-template", response_model=ProfileApplyResponse)
def apply_profile_template(
    name: str,
    template_name: str = Query(..., description="Label template name"),
    size_name: str = Query(..., description="Size variant, e.g. 'XS'"),
) -> ProfileApplyResponse:
    """Apply a profile's stored order JSON to a specific template + size."""
    from labelforge.mappings import get_ai_file
    from ..label_mapping import build_component_changes

    row = get_config(name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Config '{name}' not found.")

    raw_input_json = row.get("input_json")
    if not raw_input_json:
        raise HTTPException(
            status_code=422,
            detail="No order JSON stored for this profile. Re-save from Admin.",
        )
    order_data = _json.loads(raw_input_json)

    result = build_component_changes(template_name, order_data)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_name}' not found.",
        )

    changes_list = result.get("changes", [])
    size_names = result.get("size_names", [])
    size_index = None
    if size_names:
        for i, sn in enumerate(size_names):
            if sn == size_name:
                size_index = i
                break
    if size_index is None:
        try:
            size_index = int(size_name) - 1
        except ValueError:
            size_index = 0
    changes = changes_list[size_index] if size_index < len(changes_list) else {}

    ai_file_rel = get_ai_file(template_name)
    if ai_file_rel is None:
        raise HTTPException(
            status_code=404,
            detail=f"No AI file mapping for template '{template_name}'.",
        )
    ai_file_path = _PROJECT_ROOT / ai_file_rel
    if not ai_file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"AI file not found on server: {ai_file_rel}",
        )

    _, session, changed_count, warning_msg = _apply_changes_to_pdf(
        ai_file_path, changes, file_type="ai",
    )

    output_filename = f"{name}_{template_name}_{size_name}.pdf"
    return ProfileApplyResponse(
        session_id=session.session_id,
        size_name=size_name,
        changed_count=changed_count,
        output_filename=output_filename,
        warning=warning_msg,
    )
