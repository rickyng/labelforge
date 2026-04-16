"""Templates API — list, inspect, and apply label template mappings."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from ..apply_utils import apply_changes_to_pdf
from ..dependencies import get_session, run_analysis, rasterize_ai_preview, _text_components_to_label_dtos
from ..label_mapping import (
    build_component_changes,
    get_template_fields,
    list_templates,
    resolve_template_fields,
)
from ..schemas import (
    AnalyzeResponse,
    ComponentMapResponse,
    ProfileApplyResponse,
    ResolvedFieldsResponse,
    TemplateFieldsResponse,
    TemplatesListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Project root — resolve AI file paths relative to this
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/templates", response_model=TemplatesListResponse)
def get_templates():
    """List all available label templates."""
    return TemplatesListResponse(templates=list_templates())


@router.get("/templates/{template_name}", response_model=TemplateFieldsResponse)
def get_template(template_name: str):
    """Get fields for a specific template."""
    fields = get_template_fields(template_name)
    if fields is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found.",
        )
    return TemplateFieldsResponse(template_name=template_name, fields=fields)


@router.post(
    "/templates/{template_name}/resolve",
    response_model=ResolvedFieldsResponse,
)
async def resolve_template(
    template_name: str,
    file: UploadFile = File(...),
):
    """Upload a JSON order file and resolve all template fields against it."""
    try:
        raw = await file.read()
        order_data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {exc}",
        )

    result = resolve_template_fields(template_name, order_data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found.",
        )
    return ResolvedFieldsResponse(**result)


@router.post(
    "/templates/{template_name}/map",
    response_model=ComponentMapResponse,
)
async def map_template(
    template_name: str,
    file: UploadFile = File(...),
    session_id: str | None = Query(None),
):
    """Upload a JSON order file and produce component_id -> intended_value per size.

    If session_id is provided, the changes are stored in the session for later
    persistence (save config) and application (apply profile).
    """
    try:
        raw = await file.read()
        order_data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {exc}",
        )

    result = build_component_changes(template_name, order_data)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found.",
        )

    # Store in session so it gets used on apply-direct
    if session_id:
        session = get_session(session_id)
        changes_list = result.get("changes", [])
        size_names = result.get("size_names", [])
        sizes = []
        for i, changes in enumerate(changes_list):
            size_name = size_names[i] if i < len(size_names) else str(i + 1)
            sizes.append({"size_name": size_name, "changes": changes})
        session.extra["changes_data"] = {
            "template_name": template_name,
            "sizes": sizes,
        }
        session.extra["input_json_raw"] = raw.decode("utf-8", errors="replace")

    return ComponentMapResponse(**result)


@router.post(
    "/templates/{template_name}/load-ai",
    response_model=AnalyzeResponse,
)
def load_ai_file(
    template_name: str,
    session_id: str = Query(...),
):
    """Load the AI file associated with a template into the session and analyze it."""
    from labelforge.mappings import get_ai_file, get_grouping_mode

    # 1. Resolve AI file path
    ai_file_rel = get_ai_file(template_name)
    if ai_file_rel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI file mapping for template '{template_name}'.",
        )

    ai_file_path = _PROJECT_ROOT / ai_file_rel
    if not ai_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI file not found on server: {ai_file_rel}",
        )

    # 2. Get session, copy AI file into session dir
    session = get_session(session_id)
    dest = session.tmp_dir / "input.ai"
    shutil.copy2(ai_file_path, dest)

    # 3. Convert .ai → clean PDF (kept for apply/download pipeline)
    #    and rasterize pages to PNG for guaranteed-correct browser preview.
    import fitz
    ai_doc = fitz.open(str(dest))
    pdf_path = session.tmp_dir / "input.pdf"
    ai_doc.save(str(pdf_path))
    ai_doc.close()

    rasterize_ai_preview(session, dest)

    # 4. Update session metadata — preview uses input_path, analysis uses the same
    session.input_path = pdf_path
    session.file_type = "ai"

    # 5. Run analysis - extracts span-level components and caches them
    #    Enable OCR so outlined CJK text in shapes gets detected
    label_dtos, page_count, mapping_name = run_analysis(session, enable_ocr=True)

    # 6. Apply grouping based on template's GROUPING_MODE
    grouping_mode = get_grouping_mode(template_name)
    if grouping_mode != "span":
        from labelforge.document_analyzer import group_text_components
        from labelforge.component_models import ComponentType
        from ..schemas import LabelDTO

        # Get span-level components from session cache
        span_components = session.extra.get("components", [])
        if span_components:
            # Group for display
            grouped_components = group_text_components(span_components, grouping_mode)
            # Derive LabelDTOs from grouped components
            label_dtos = _text_components_to_label_dtos(grouped_components)
            # Keep span-level in a separate key for apply pipeline
            session.extra["components_span"] = span_components

    logger.info(
        "Load-AI: template=%s session=%s labels=%d grouping=%s",
        template_name, session_id, len(label_dtos), grouping_mode,
    )

    return AnalyzeResponse(
        session_id=session_id,
        labels=label_dtos,
        page_count=page_count,
        file_type="ai",
        editable_ids=[],
        warning=None,
        mapping_name=mapping_name,
        grouping_mode=grouping_mode,
    )


@router.post(
    "/templates/{template_name}/apply-direct",
    response_model=ProfileApplyResponse,
)
def apply_direct(
    template_name: str,
    session_id: str = Query(..., description="Session with mapping data"),
    size_index: int = Query(0, description="Index into the size list"),
):
    """Apply template changes directly from session data (no saved profile needed).

    The session must have mapping data from a prior call to the map endpoint.
    """
    from labelforge.mappings import get_ai_file

    session = get_session(session_id)
    changes_data = session.extra.get("changes_data")
    if not changes_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No mapping data in session. Upload order JSON and map first.",
        )

    sizes = changes_data.get("sizes", [])
    if size_index < 0 or size_index >= len(sizes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Size index {size_index} out of range (0–{len(sizes) - 1}).",
        )

    changes = sizes[size_index]["changes"]
    size_name = sizes[size_index].get("size_name", str(size_index + 1))

    # Resolve AI file
    ai_file_rel = get_ai_file(template_name)
    if ai_file_rel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI file mapping for template '{template_name}'.",
        )
    ai_file_path = _PROJECT_ROOT / ai_file_rel
    if not ai_file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI file not found on server: {ai_file_rel}",
        )

    output_path, new_session, changed_count, warning_msg = apply_changes_to_pdf(
        ai_file_path, changes, file_type="ai",
    )

    output_filename = f"{template_name}_{size_name}.pdf"
    logger.info(
        "Apply-direct: template=%s size=%s session=%s changed=%d",
        template_name, size_name, new_session.session_id, changed_count,
    )

    return ProfileApplyResponse(
        session_id=new_session.session_id,
        size_name=size_name,
        changed_count=changed_count,
        output_filename=output_filename,
        warning=warning_msg,
    )
