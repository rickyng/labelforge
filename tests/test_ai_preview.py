"""Test that all .ai template files can be previewed correctly in admin/user view.

Verifies the .ai → PDF conversion pipeline used by the backend:
  1. PyMuPDF opens the file
  2. fitz.save() produces a valid clean PDF
  3. Text / span content is identical before and after conversion
  4. Rendering to pixmap works
  5. Full component extraction produces valid TEXT components
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz
import pytest

from labelforge.component_models import ComponentType
from labelforge.document_analyzer import extract_components

logging.getLogger("fitz").setLevel(logging.WARNING)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "labelforge" / "templates"


def _extract_spans(page: fitz.Page) -> list[dict]:
    """Extract text spans from a page, returning [{text, bbox}, ...]."""
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
    spans = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                spans.append({
                    "text": span.get("text", ""),
                    "bbox": span.get("bbox", (0, 0, 0, 0)),
                })
    return spans


def _convert_ai_to_pdf(ai_path: Path, out_path: Path) -> None:
    """Convert .ai to clean PDF (mirrors backend load-ai endpoint)."""
    doc = fitz.open(str(ai_path))
    doc.save(str(out_path))
    doc.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(params=list(TEMPLATES_DIR.glob("*.ai")), ids=lambda p: p.stem)
def ai_path(request) -> Path:
    """Parametrized fixture: each .ai template file."""
    return request.param


@pytest.fixture()
def converted_pdf(ai_path: Path, tmp_path: Path) -> Path:
    """The .ai file converted to a clean PDF."""
    pdf_path = tmp_path / "converted.pdf"
    _convert_ai_to_pdf(ai_path, pdf_path)
    return pdf_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_converted_pdf_has_same_page_count(ai_path: Path, converted_pdf: Path):
    with fitz.open(str(ai_path)) as ai, fitz.open(str(converted_pdf)) as pdf:
        assert pdf.page_count == ai.page_count


def test_converted_pdf_preserves_text(ai_path: Path, converted_pdf: Path):
    """Full text and per-span content must be identical after .ai → PDF conversion."""
    with fitz.open(str(ai_path)) as ai, fitz.open(str(converted_pdf)) as pdf:
        for page_num in range(ai.page_count):
            page_ai, page_pdf = ai[page_num], pdf[page_num]

            assert page_ai.get_text("text") == page_pdf.get_text("text")

            spans_ai = _extract_spans(page_ai)
            spans_pdf = _extract_spans(page_pdf)
            assert len(spans_ai) == len(spans_pdf)

            for i, (sa, sp) in enumerate(zip(spans_ai, spans_pdf)):
                assert sa["text"] == sp["text"], f"page {page_num} span {i}: text mismatch"
                for j in range(4):
                    assert abs(sa["bbox"][j] - sp["bbox"][j]) < 0.5, (
                        f"page {page_num} span {i}: bbox[{j}] {sa['bbox'][j]} vs {sp['bbox'][j]}"
                    )


def test_render_to_pixmap(ai_path: Path):
    """Rendering at 150 DPI must succeed (PDF.js preview path)."""
    with fitz.open(str(ai_path)) as doc:
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
        assert pix.width > 0 and pix.height > 0


def test_component_extraction(ai_path: Path):
    """Full component extraction must yield valid TEXT components."""
    with fitz.open(str(ai_path)) as doc:
        components = extract_components(doc)

    assert len(components) >= 1

    for tc in (c for c in components if c.type == ComponentType.TEXT):
        assert tc.id
        assert tc.bbox[2] > tc.bbox[0]
        assert tc.bbox[3] > tc.bbox[1]
        assert tc.text is not None


def test_expected_templates_exist():
    """All known template files must be present in the templates directory."""
    stems = {f.stem for f in TEMPLATES_DIR.glob("*.ai")}
    for expected in ["ADHEDIST-mango_edit_no1_v2", "GI001BAW-GI001BAC_ai", "PVPV0102-PVP002XG_ai"]:
        assert expected in stems, f"Missing template: {expected}"
