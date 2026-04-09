"""CRUD endpoints for user labels (named text-replacement sets)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..db import delete_user_label, get_config, get_user_label, list_user_labels, save_user_label
from ..dependencies import create_session, _text_components_to_label_dtos
from ..schemas import LoadUserLabelResponse, SaveUserLabelBody, UserLabelSummary
from ..utils import make_session_dir

router = APIRouter()


@router.get("/labels", response_model=list[UserLabelSummary])
def list_labels() -> list[UserLabelSummary]:
    """List all saved user labels."""
    return [UserLabelSummary(**row) for row in list_user_labels()]


@router.get("/labels/{name:path}", response_model=LoadUserLabelResponse)
def load_label(
    name: str,
) -> LoadUserLabelResponse:
    """Load a user label — restores the profile session and applies saved fills."""
    row = get_user_label(name)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Label '{name}' not found.")

    profile = get_config(row["profile_name"])
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{row['profile_name']}' not found. Re-save this label to link a valid profile.",
        )
    if not profile.get("file_blob"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No file stored for this profile.",
        )

    # Restore file to a new temp session
    tmp_dir = make_session_dir()
    suffix = ".ai" if profile["file_type"] == "ai" else ".pdf"
    input_path = tmp_dir / f"input{suffix}"
    input_path.write_bytes(profile["file_blob"])
    session = create_session(input_path=input_path, file_type=profile["file_type"], tmp_dir=tmp_dir)

    # Extract components (single source of truth)
    import fitz
    from labelforge.document_analyzer import extract_components
    doc = fitz.open(str(input_path))
    components = extract_components(doc)
    doc.close()
    session.extra["components"] = components

    fills = row["fills"]
    label_dtos = _text_components_to_label_dtos(components, fills)

    return LoadUserLabelResponse(
        session_id=session.session_id,
        labels=label_dtos,
        page_count=profile["page_count"],
        file_type=profile["file_type"],
        editable_ids=profile["editable_ids"],
        warning=None,
        label_name=name,
        profile_name=row["profile_name"],
    )


@router.post("/labels/{name:path}", status_code=status.HTTP_204_NO_CONTENT)
def upsert_label(
    name: str,
    body: SaveUserLabelBody,
) -> None:
    """Create or update a user label."""
    save_user_label(name=name, profile_name=body.profile_name, fills=body.fills)


@router.delete("/labels/{name:path}", status_code=status.HTTP_204_NO_CONTENT)
def remove_label(
    name: str,
) -> None:
    """Delete a user label."""
    if not delete_user_label(name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Label '{name}' not found.")
