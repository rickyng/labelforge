"""Shared apply utility — used by both configs and templates routers."""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz
import json as _json

from labelforge.applier import apply_from_components
from labelforge.component_models import ComponentType, ComponentsFile
from labelforge.document_analyzer import extract_components

from .dependencies import create_session, SessionData, rasterize_ai_preview
from .utils import make_session_dir


def apply_changes_to_pdf(
    input_path: Path,
    changes: dict[str, str],
    file_type: str = "ai",
) -> tuple[Path, SessionData, int, str | None]:
    """Extract components, remap label→component IDs, apply changes, return result.

    Returns (output_path, session, changed_count, warning_msg).
    """
    tmp_dir = make_session_dir()
    dest = tmp_dir / f"input{'.ai' if file_type == 'ai' else '.pdf'}"
    if input_path != dest:
        shutil.copy2(input_path, dest)

    doc = fitz.open(str(dest))
    all_components = extract_components(doc)
    doc.close()

    cf = ComponentsFile(source_file=str(dest), components=all_components)
    components_path = tmp_dir / "components.json"
    components_path.write_text(cf.model_dump_json(), encoding="utf-8")

    # Build set of all valid component IDs for direct lookup
    comp_ids = {c.id for c in all_components}

    # Legacy remap: label IDs (p0_b...) → component IDs (p0_t_b...)
    label_to_comp = {
        c.id.replace("_t_b", "_b"): c.id
        for c in all_components if c.type == ComponentType.TEXT
    }

    filtered_changes = {}
    for k, v in changes.items():
        if k in comp_ids:
            # Key is already a valid component ID (current mapping files)
            filtered_changes[k] = v
        elif k in label_to_comp:
            # Legacy format key (p0_b... → p0_t_b...)
            filtered_changes[label_to_comp[k]] = v

    changes_path = tmp_dir / "changes.json"
    changes_path.write_text(_json.dumps(filtered_changes), encoding="utf-8")

    output_path = tmp_dir / "output.pdf"
    font_warnings: list[str] = []
    changed_count = apply_from_components(
        Path(str(components_path)),
        Path(str(changes_path)),
        Path(str(output_path)),
        font_warnings=font_warnings,
    )

    session = create_session(input_path=dest, file_type=file_type, tmp_dir=tmp_dir)
    session.output_path = output_path

    # Rasterize output to PNG so frontend preview has consistent sizing
    rasterize_ai_preview(session, output_path)

    warning_msg = (
        "Font substitution applied for some labels: embedded font missing glyphs for new text. "
        "Affected labels: " + ", ".join(
            w.split("'")[1] for w in font_warnings if "'" in w
        )
    ) if font_warnings else None

    return output_path, session, changed_count, warning_msg
