"""CRUD endpoints for persisted editable configs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..db import delete_config, get_config, list_configs, update_name
from ..dependencies import create_session, require_role
from ..schemas import AnalyzeResponse, ConfigSummary, LabelDTO
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

    label_dtos = [LabelDTO(**lbl) for lbl in row["labels"]]
    return AnalyzeResponse(
        session_id=session.session_id,
        labels=label_dtos,
        page_count=row["page_count"],
        file_type=row["file_type"],
        editable_ids=row["editable_ids"],
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
