"""CRUD endpoints for persisted editable configs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from ..utils import make_session_dir
from pydantic import BaseModel

from ..db import delete_config, get_config, list_configs, update_name
from ..dependencies import create_session, require_role
from ..schemas import AnalyzeResponse, ConfigSummary, LabelDTO, ProfileApplyResponse
from ..utils import make_session_dir

router = APIRouter()


@router.get("/configs", response_model=list[ConfigSummary])
def list_all_configs(_role: str = Depends(require_role)) -> list[ConfigSummary]:
    """List all saved editable configs."""
    return [ConfigSummary(**row) for row in list_configs()]


@router.get("/configs/{name:path}", response_model=AnalyzeResponse)
def load_config(
    name: str,
    _role: str = Depends(require_role),
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

    session = create_session(input_path=input_path, file_type=row["file_type"], tmp_dir=tmp_dir)

    # Run analyze so the session has a labels_json_path for later re-save
    from labelforge.analyzer import analyze_file
    labels_json_path = tmp_dir / "labels.json"
    analyze_file(input_path=input_path, output_path=labels_json_path, min_font_size=0.0, pretty=True)
    session.labels_json_path = labels_json_path

    import json as _json
    label_dtos = [LabelDTO(**lbl) for lbl in row["labels"]]
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
    )


class RenameBody(BaseModel):
    name: str


@router.patch("/configs/{name:path}/name", status_code=status.HTTP_204_NO_CONTENT)
def rename_config(
    name: str,
    body: RenameBody,
    _role: str = Depends(require_role),
) -> None:
    """Rename a profile."""
    if not update_name(name, body.name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config '{name}' not found.")


@router.delete("/configs/{name:path}", status_code=status.HTTP_204_NO_CONTENT)
def remove_config(
    name: str,
    _role: str = Depends(require_role),
) -> None:
    """Delete a saved config entry."""
    if not delete_config(name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config '{name}' not found.")


@router.post("/configs/{name:path}/apply", response_model=ProfileApplyResponse)
def apply_profile(
    name: str,
    size_name: str = Query(..., description="Size variant, e.g. 'XS'"),
    _role: str = Depends(require_role),
) -> ProfileApplyResponse:
    import json as _json
    import re as _re
    import fitz
    from labelforge.applier import apply_from_components
    from labelforge.document_analyzer import extract_components
    from labelforge.component_models import ComponentType, BarcodeFormat as _BFmt

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

    import json as _json2
    from pathlib import Path as _Path
    from labelforge.component_models import ComponentsFile

    doc = fitz.open(str(input_path))
    all_components = extract_components(doc)
    doc.close()

    # Build components.json
    cf = ComponentsFile(source_file=str(input_path), components=all_components)
    components_path = tmp_dir / "components.json"
    components_path.write_text(cf.model_dump_json(), encoding="utf-8")

    # Build changes.json — remap label IDs (p0_b...) to component IDs (p0_t_b...)
    label_to_comp = {
        c.id.replace("_t_b", "_b"): c.id
        for c in all_components if c.type == ComponentType.TEXT
    }
    filtered_changes = {
        label_to_comp[k]: v
        for k, v in changes.items()
        if k in label_to_comp
    }
    # Also update barcode image components when the new value is an EAN-13.
    # The barcode graphic is a separate BARCODE component from the text span;
    # match by detecting 13-digit values rather than by original text equality
    # (the barcode image and the text span may have different current values).
    ean13_new_values = {
        v for v in filtered_changes.values() if _re.fullmatch(r'\d{13}', v)
    }
    if ean13_new_values:
        ean13_barcode_comps = [
            c for c in all_components
            if c.type == ComponentType.BARCODE and c.barcode_format == _BFmt.EAN13
        ]
        for ean_value in ean13_new_values:
            for bc in ean13_barcode_comps:
                filtered_changes[bc.id] = ean_value
    changes_path = tmp_dir / "changes.json"
    changes_path.write_text(_json2.dumps(filtered_changes), encoding="utf-8")

    output_path = tmp_dir / "output.pdf"
    _font_warnings: list[str] = []
    changed_count = apply_from_components(
        _Path(str(components_path)),
        _Path(str(changes_path)),
        _Path(str(output_path)),
        font_warnings=_font_warnings,
    )

    session = create_session(input_path=input_path, file_type=row["file_type"], tmp_dir=tmp_dir)
    session.output_path = output_path
    output_filename = f"{name}_{size_name}.pdf"
    warning_msg = (
        "Font substitution applied for some labels: embedded font missing glyphs for new text. "
        "Affected labels: " + ", ".join(
            w.split("'")[1] for w in _font_warnings if "'" in w
        )
    ) if _font_warnings else None
    return ProfileApplyResponse(
        session_id=session.session_id,
        size_name=size_name,
        changed_count=changed_count,
        output_filename=output_filename,
        warning=warning_msg,
    )
