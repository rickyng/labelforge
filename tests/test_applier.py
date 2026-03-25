"""Tests for labelforge.applier."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from labelforge.analyzer import extract_labels
from labelforge.applier import apply_labels, load_labels
from labelforge.models import Label


def _extract_texts(pdf_path: Path) -> list[str]:
    """Helper: extract all non-empty text spans from a PDF."""
    doc = fitz.open(str(pdf_path))
    texts: list[str] = []
    for page in doc:
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if t:
                        texts.append(t)
    doc.close()
    return texts


# ---------------------------------------------------------------------------
# load_labels
# ---------------------------------------------------------------------------


def test_load_labels_roundtrip(sample_labels_json: Path) -> None:
    labels = load_labels(sample_labels_json)
    assert len(labels) >= 1
    assert all(isinstance(lbl, Label) for lbl in labels)


def test_load_labels_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_labels(tmp_path / "ghost.json")


def test_load_labels_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(Exception):  # json.JSONDecodeError
        load_labels(bad)


def test_load_labels_not_a_list(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"foo": "bar"}))
    with pytest.raises(ValueError, match="top-level array"):
        load_labels(bad)


# ---------------------------------------------------------------------------
# apply_labels
# ---------------------------------------------------------------------------


def test_apply_replaces_text(sample_pdf: Path, tmp_path: Path) -> None:
    """Replacing a span's text should appear in the output PDF."""
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()

    # Replace the first label
    labels[0].new_text = "REPLACED"
    out = tmp_path / "out.pdf"
    n = apply_labels(sample_pdf, labels, out, force=True)

    assert n == 1
    assert out.exists()
    texts = _extract_texts(out)
    assert "REPLACED" in texts


def test_apply_erase_only(sample_pdf: Path, tmp_path: Path) -> None:
    """Setting new_text='' should erase the span with no replacement."""
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()

    original = labels[0].original_text
    labels[0].new_text = ""
    out = tmp_path / "erased.pdf"
    n = apply_labels(sample_pdf, labels, out, force=True)

    assert n == 1
    texts = _extract_texts(out)
    assert original not in texts


def test_apply_null_skips(sample_pdf: Path, tmp_path: Path) -> None:
    """Labels with new_text=None must not modify the PDF."""
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()

    # All new_text are None by default
    assert all(lbl.new_text is None for lbl in labels)
    out = tmp_path / "unchanged.pdf"
    n = apply_labels(sample_pdf, labels, out, force=True)

    assert n == 0
    # Output is a copy of input — original texts still present
    original_texts = set(_extract_texts(sample_pdf))
    output_texts = set(_extract_texts(out))
    assert original_texts == output_texts


def test_apply_backup_flag(sample_pdf: Path, tmp_path: Path) -> None:
    """--backup should create a .bak copy of the input PDF."""
    # Copy sample to tmp so the .bak appears in a writable location
    import shutil
    src = tmp_path / "input.pdf"
    shutil.copy2(sample_pdf, src)

    doc = fitz.open(str(src))
    labels = extract_labels(doc)
    doc.close()
    labels[0].new_text = "BKP"

    out = tmp_path / "out.pdf"
    apply_labels(src, labels, out, backup=True, force=True)

    bak = src.with_suffix(".pdf.bak")
    assert bak.exists(), "Backup file should be created"


def test_apply_force_flag(sample_pdf: Path, tmp_path: Path) -> None:
    """Without --force, should raise FileExistsError if output exists."""
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    labels[0].new_text = "X"

    out = tmp_path / "exists.pdf"
    out.write_bytes(b"%PDF-1.4")

    with pytest.raises(FileExistsError):
        apply_labels(sample_pdf, labels, out, force=False)


def test_apply_force_overwrites(sample_pdf: Path, tmp_path: Path) -> None:
    """With --force, existing output file should be overwritten."""
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()
    labels[0].new_text = "FORCED"

    out = tmp_path / "overwrite.pdf"
    out.write_bytes(b"%PDF-1.4")

    n = apply_labels(sample_pdf, labels, out, force=True)
    assert n == 1
    texts = _extract_texts(out)
    assert "FORCED" in texts


def test_apply_input_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        apply_labels(
            tmp_path / "ghost.pdf",
            [],
            tmp_path / "out.pdf",
            force=True,
        )


def test_apply_returns_correct_count(sample_pdf: Path, tmp_path: Path) -> None:
    doc = fitz.open(str(sample_pdf))
    labels = extract_labels(doc)
    doc.close()

    # Change all labels
    for i, lbl in enumerate(labels):
        lbl.new_text = f"New{i}"

    out = tmp_path / "all_changed.pdf"
    n = apply_labels(sample_pdf, labels, out, force=True)
    assert n == len(labels)
