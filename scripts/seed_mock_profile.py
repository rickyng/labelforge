#!/usr/bin/env python3
"""Seed a mock profile into the LabelForge SQLite DB.

Builds a minimal in-memory PDF with two text spans, extracts components
from it, constructs fake XS and M size changes, then upserts the profile
via save_config.

Usage:
    python scripts/seed_mock_profile.py
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF

from backend.db import init_db, save_config
from labelforge.document_analyzer import extract_components
from labelforge.component_models import ComponentType

# --- build a minimal in-memory PDF ---

PROFILE_NAME = "mock-tshirt"
FILENAME = "mock_tshirt.pdf"

SPANS = [
    {"text": "T-Shirt Label", "x": 50, "y": 700, "fontsize": 18},
    {"text": "100% Cotton",   "x": 50, "y": 670, "fontsize": 12},
    {"text": "Made in USA",   "x": 50, "y": 650, "fontsize": 12},
]


def build_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=200, height=800)
    for span in SPANS:
        page.insert_text(
            (span["x"], span["y"]),
            span["text"],
            fontsize=span["fontsize"],
            color=(0, 0, 0),
        )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def main() -> None:
    init_db()

    pdf_bytes = build_pdf()

    # Re-open from bytes so extract_components can parse it
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        components = extract_components(doc)
    finally:
        doc.close()

    text_components = [c for c in components if c.type == ComponentType.TEXT]
    print(f"Extracted {len(text_components)} TEXT component(s)")

    if not text_components:
        print("ERROR: no text components extracted — aborting seed.", file=sys.stderr)
        sys.exit(1)

    # Build fake per-size changes
    # XS: prepend "XS " to every text span
    # M:  prepend "M "  to every text span
    xs_changes: dict[str, str] = {}
    m_changes:  dict[str, str] = {}
    editable_ids: list[str] = []
    for comp in text_components:
        cid = comp.id
        original = comp.text or ""
        xs_changes[cid] = f"XS {original}"
        m_changes[cid]  = f"M {original}"
        editable_ids.append(cid)

    changes_data = {
        "source_file": FILENAME,
        "style_id":    "MOCK001",
        "color_code":  "BLK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sizes": [
            {"size_name": "XS", "changes": xs_changes},
            {"size_name": "M",  "changes": m_changes},
        ],
    }

    # Build label dicts compatible with LabelDTO
    labels: list[dict] = []
    for comp in text_components:
        labels.append({
            "id":            comp.id,
            "page":          comp.page,
            "bbox":          list(comp.bbox),
            "original_text": comp.text or "",
            "new_text":      None,
            "fontname":      comp.fontname or "helv",
            "fontsize":      comp.fontsize or 12.0,
            "color":         comp.color or "#000000",
            "flags":         comp.flags or 0,
            "rotation":      comp.rotation or 0,
            "origin":        comp.origin,
        })

    save_config(
        name=PROFILE_NAME,
        filename=FILENAME,
        labels=labels,
        editable_ids=editable_ids,
        file_blob=pdf_bytes,
        page_count=1,
        file_type="pdf",
        changes_json=json.dumps(changes_data),
    )

    print(f"Seeded profile '{PROFILE_NAME}' with {len(text_components)} labels "
          f"and sizes: XS, M")


if __name__ == "__main__":
    main()
