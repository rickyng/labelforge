"""Tests for labelforge.analyzer."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from labelforge.analyzer import extract_labels, analyze_pdf, _parse_page_range
from labelforge.models import Label


# ---------------------------------------------------------------------------
# _parse_page_range
# ---------------------------------------------------------------------------


def test_parse_page_range_single() -> None:
    assert _parse_page_range("2", 5) == [2]


def test_parse_page_range_range() -> None:
    assert _parse_page_range("0-2", 5) == [0, 1, 2]


def test_parse_page_range_csv() -> None:
    assert _parse_page_range("0,2,4", 5) == [0, 2, 4]


def test_parse_page_range_clamps_to_total() -> None:
    result = _parse_page_range("0-10", 3)
    assert result == [0, 1, 2]


def test_parse_page_range_all_out_of_range() -> None:
    with pytest.raises(ValueError, match="no valid pages"):
        _parse_page_range("10-20", 3)


# ---------------------------------------------------------------------------
# extract_labels
# ---------------------------------------------------------------------------


def test_extract_returns_labels(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    assert len(labels) >= 2, "Expected at least 2 spans in sample PDF"


def test_all_labels_are_label_instances(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    assert all(isinstance(lbl, Label) for lbl in labels)


def test_label_ids_are_unique(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    ids = [lbl.id for lbl in labels]
    assert len(ids) == len(set(ids)), "Label IDs must be unique"


def test_color_is_valid_hex(sample_pdf: Path) -> None:
    import re
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    hex_re = re.compile(r"^#[0-9a-f]{6}$")
    for lbl in labels:
        assert hex_re.match(lbl.color), f"Invalid color: {lbl.color} for label {lbl.id}"


def test_new_text_is_none_by_default(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    assert all(lbl.new_text is None for lbl in labels)


def test_min_font_size_filter(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    all_labels = extract_labels(doc, min_font_size=0.0)
    filtered = extract_labels(doc, min_font_size=999.0)
    doc.close()
    assert len(filtered) == 0
    assert len(all_labels) >= 1


def test_page_range_filter(sample_pdf_multipage: Path) -> None:
    doc = fitz.open(str(sample_pdf_multipage))
    labels = extract_labels(doc, page_range=[0])
    doc.close()
    assert all(lbl.page == 0 for lbl in labels)


def test_page_range_all_pages(sample_pdf_multipage: Path) -> None:
    doc = fitz.open(str(sample_pdf_multipage))
    labels_all = extract_labels(doc)
    labels_range = extract_labels(doc, page_range=[0, 1, 2])
    doc.close()
    assert len(labels_all) == len(labels_range)


def test_bbox_has_four_elements(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    for lbl in labels:
        assert len(lbl.bbox) == 4


def test_fontsize_positive(sample_pdf: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    assert all(lbl.fontsize > 0 for lbl in labels)


# ---------------------------------------------------------------------------
# analyze_pdf (high-level)
# ---------------------------------------------------------------------------


def test_analyze_pdf_writes_json(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    count = analyze_pdf(sample_pdf, out)
    assert out.exists()
    assert count >= 2


def test_analyze_pdf_json_is_valid(sample_pdf: Path, tmp_path: Path) -> None:
    import json
    out = tmp_path / "out.json"
    analyze_pdf(sample_pdf, out)
    with out.open() as fh:
        data = json.load(fh)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "original_text" in data[0]
    assert "new_text" in data[0]


def test_analyze_pdf_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        analyze_pdf(tmp_path / "ghost.pdf", tmp_path / "out.json")


def test_analyze_pdf_pretty_indent(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "pretty.json"
    analyze_pdf(sample_pdf, out, pretty=True)
    raw = out.read_text()
    assert "\n  " in raw  # indented


def test_analyze_pdf_compact(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "compact.json"
    analyze_pdf(sample_pdf, out, pretty=False)
    raw = out.read_text()
    assert raw.startswith("[")  # still valid JSON
