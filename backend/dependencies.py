"""Shared session store and dependency injectors."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status


@dataclass
class SessionData:
    session_id: str
    input_path: Path        # original upload — never mutated
    file_type: str          # "pdf", "ai", or "json"
    tmp_dir: Path
    output_path: Path | None = None   # latest processed output
    labels_json_path: Path | None = None
    preview_images: dict[int, Path] = field(default_factory=dict)  # page_num -> PNG path (for .ai rasterized preview)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def working_path(self) -> Path:
        """The file to use as input for the next processing step."""
        if self.output_path and self.output_path.exists():
            return self.output_path
        return self.input_path


# In-memory session store: sid -> SessionData
SESSION_STORE: dict[str, SessionData] = {}

# Editable config store: filename -> list of editable label IDs
EDITABLE_CONFIG: dict[str, list[str]] = {}

def create_session(input_path: Path, file_type: str, tmp_dir: Path) -> SessionData:
    sid = str(uuid.uuid4())
    session = SessionData(
        session_id=sid,
        input_path=input_path,
        file_type=file_type,
        tmp_dir=tmp_dir,
    )
    SESSION_STORE[sid] = session
    return session


def get_session(session_id: str) -> SessionData:
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or expired.",
        )
    return session


def rasterize_ai_preview(session: SessionData, ai_path: Path, dpi: int = 150) -> None:
    """Rasterize all pages of an .ai file to PNG for PDF.js-compatible preview."""
    import fitz

    doc = fitz.open(str(ai_path))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for page_num in range(doc.page_count):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_path = session.tmp_dir / f"preview_p{page_num}.png"
        pix.save(str(png_path))
        session.preview_images[page_num] = png_path
    doc.close()


def _text_components_to_label_dtos(components, fills: dict[str, str] | None = None) -> list:
    """Derive LabelDTOs from TEXT components. Shared across routers."""
    from labelforge.component_models import ComponentType
    from .schemas import LabelDTO
    fills = fills or {}
    return [
        LabelDTO(
            id=c.id,
            page=c.page,
            bbox=list(c.bbox),
            original_text=c.text or "",
            new_text=fills.get(c.id),
            fontname=c.fontname or "helv",
            fontsize=c.fontsize or 10.0,
            color=c.color or "#000000",
            flags=c.flags or 0,
            rotation=c.rotation or 0,
            origin=list(c.origin) if c.origin else None,
        )
        for c in components
        if c.type == ComponentType.TEXT
    ]


def run_analysis(session: SessionData) -> tuple[list, int, str | None]:
    """Run component extraction on the session's input file.

    Returns (label_dtos, page_count, mapping_name).
    Derives LabelDTOs from TEXT components (single source of truth).
    """
    import fitz
    from labelforge.document_analyzer import extract_components
    from labelforge.mappings import detect_mapping

    doc = fitz.open(str(session.input_path))
    page_count = doc.page_count
    components = extract_components(doc)
    doc.close()

    session.extra["components"] = components

    component_ids = {c.id for c in components}
    mapping_name = detect_mapping(component_ids)
    session.extra["mapping_name"] = mapping_name

    return _text_components_to_label_dtos(components), page_count, mapping_name
