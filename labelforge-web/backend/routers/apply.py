"""POST /api/apply/{session_id} — apply edited labels and produce output file."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from labelforge.applier import apply_labels
from labelforge.models import Label
from labelforge.utils import AI_OUTPUT_WARNING

from ..dependencies import SessionData, get_session
from ..schemas import ApplyRequest, ApplyResponse

router = APIRouter()


@router.post("/apply/{session_id}", response_model=ApplyResponse)
def apply_session(session_id: str, body: ApplyRequest) -> ApplyResponse:
    """Apply label edits to the uploaded file. Returns output filename for download."""
    session: SessionData = get_session(session_id)

    labels: list[Label] = []
    for dto in body.labels:
        try:
            lbl = Label.model_validate(dto.model_dump())
            labels.append(lbl)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid label '{dto.id}': {exc}",
            ) from exc

    out_ext = ".ai" if body.output_format == "ai" else ".pdf"
    output_path = session.tmp_dir / f"output{out_ext}"

    if output_path.exists():
        output_path.unlink()

    try:
        changed_count = apply_labels(
            input_path=session.input_path,
            labels=labels,
            output_path=output_path,
            backup=False,
            force=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Apply failed: {exc}",
        ) from exc

    session.output_path = output_path

    warning = AI_OUTPUT_WARNING if body.output_format == "ai" else None

    return ApplyResponse(
        session_id=session_id,
        changed_count=changed_count,
        output_filename=output_path.name,
        warning=warning,
    )
