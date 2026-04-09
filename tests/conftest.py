"""Shared pytest fixtures for LabelForge tests."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a minimal single-page PDF with two text spans.

    Page size: 200x100 pts
    Span 1: "Hello World" at (10, 10, 100, 24) in black, Helvetica 12pt
    Span 2: "Goodbye" at (10, 40, 70, 54) in red, Helvetica-Bold 10pt
    """
    tmp = tmp_path_factory.mktemp("fixtures")
    pdf_path = tmp / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page(width=200, height=100)

    # Span 1: black text
    page.insert_text(
        fitz.Point(10, 22),
        "Hello World",
        fontname="helv",
        fontsize=12,
        color=(0, 0, 0),
    )

    # Span 2: red text
    page.insert_text(
        fitz.Point(10, 52),
        "Goodbye",
        fontname="hebo",
        fontsize=10,
        color=(1, 0, 0),
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture(scope="session")
def sample_pdf_multipage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a 3-page PDF with one text span per page."""
    tmp = tmp_path_factory.mktemp("fixtures_multi")
    pdf_path = tmp / "multipage.pdf"

    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=200, height=100)
        page.insert_text(
            fitz.Point(10, 22),
            f"Page {i} text",
            fontname="helv",
            fontsize=12,
            color=(0, 0, 0),
        )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def sample_labels_json(tmp_path: Path, sample_pdf: Path) -> Path:
    """Write a labels.json extracted from the sample PDF."""
    import fitz as _fitz
    from labelforge.analyzer import extract_labels

    doc = _fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()

    json_path = tmp_path / "labels.json"
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump([lbl.model_dump() for lbl in labels], fh, indent=2)
    return json_path
