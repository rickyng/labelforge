"""POST /api/analyze/{session_id} — extract labels from uploaded file."""

from __future__ import annotations

import fitz
from fastapi import APIRouter

from labelforge.analyzer import analyze_file
from labelforge.applier import load_labels
from labelforge.utils import AI_COMPAT_WARNING

from fastapi import HTTPException, status

from ..dependencies import CURRENT_SESSION_ID, EDITABLE_CONFIG, SESSION_STORE, SessionData, get_session, set_current_session
from ..schemas import AnalyzeResponse, LabelDTO

router = APIRouter()


@router.post("/analyze/{session_id}", response_model=AnalyzeResponse)
def analyze_session(session_id: str) -> AnalyzeResponse:
    """Run label extraction on the uploaded file. Returns all labels as JSON."""
    session: SessionData = get_session(session_id)

    labels_json_path = session.tmp_dir / "labels.json"
    analyze_file(
        input_path=session.input_path,
        output_path=labels_json_path,
        min_font_size=0.0,
        pretty=True,
    )
    session.labels_json_path = labels_json_path

    labels = load_labels(labels_json_path)

    doc = fitz.open(str(session.input_path))
    page_count = doc.page_count
    doc.close()

    label_dtos = [
        LabelDTO(
            id=lbl.id,
            page=lbl.page,
            bbox=list(lbl.bbox),
            original_text=lbl.original_text,
            new_text=lbl.new_text,
            fontname=lbl.fontname,
            fontsize=lbl.fontsize,
            color=lbl.color,
            flags=lbl.flags,
            rotation=lbl.rotation,
            origin=list(lbl.origin) if lbl.origin else None,
            auto_fit=lbl.auto_fit,
            max_scale_down=lbl.max_scale_down,
            padding=lbl.padding,
            white_out=lbl.white_out,
        )
        for lbl in labels
    ]

    warning = AI_COMPAT_WARNING if session.file_type == "ai" else None
    filename = session.input_path.name
    editable_ids = EDITABLE_CONFIG.get(filename, [])
    set_current_session(session_id)

    return AnalyzeResponse(
        session_id=session_id,
        labels=label_dtos,
        page_count=page_count,
        file_type=session.file_type,
        editable_ids=editable_ids,
        warning=warning,
    )


@router.get("/session/current", response_model=AnalyzeResponse)
def get_current_session() -> AnalyzeResponse:
    """Return the most recently analyzed session for the User view."""
    from ..dependencies import CURRENT_SESSION_ID as _cur
    if _cur is None or _cur not in SESSION_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session. Admin must upload and analyze a file first.",
        )
    session: SessionData = SESSION_STORE[_cur]
    if session.labels_json_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session has no labels yet.",
        )
    from labelforge.applier import load_labels
    import fitz
    labels = load_labels(session.labels_json_path)
    doc = fitz.open(str(session.input_path))
    page_count = doc.page_count
    doc.close()
    filename = session.input_path.name
    editable_ids = EDITABLE_CONFIG.get(filename, [])
    label_dtos = [
        LabelDTO(
            id=lbl.id,
            page=lbl.page,
            bbox=list(lbl.bbox),
            original_text=lbl.original_text,
            new_text=lbl.new_text,
            fontname=lbl.fontname,
            fontsize=lbl.fontsize,
            color=lbl.color,
            flags=lbl.flags,
            rotation=lbl.rotation,
            origin=list(lbl.origin) if lbl.origin else None,
            auto_fit=lbl.auto_fit,
            max_scale_down=lbl.max_scale_down,
            padding=lbl.padding,
            white_out=lbl.white_out,
        )
        for lbl in labels
    ]
    return AnalyzeResponse(
        session_id=_cur,
        labels=label_dtos,
        page_count=page_count,
        file_type=session.file_type,
        editable_ids=editable_ids,
        warning=None,
    )
