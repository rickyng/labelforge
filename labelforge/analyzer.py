"""PDF → labels.json extraction logic."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import fitz  # PyMuPDF

from .models import Label
from .utils import bbox_is_degenerate, int_color_to_hex, detect_file_type, AI_COMPAT_WARNING

logger = logging.getLogger(__name__)


def _parse_page_range(spec: str, total_pages: int) -> list[int]:
    """Parse a page range spec like '0-5' or '0,2,4' into a sorted list of page indices.

    Args:
        spec: Range string, e.g. '0-5', '0,1,3', or '2'.
        total_pages: Total number of pages in the document (for bounds checking).

    Returns:
        Sorted list of valid 0-based page indices.

    Raises:
        ValueError: If the spec is malformed or all indices are out of range.
    """
    indices: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            indices.update(range(int(lo), int(hi) + 1))
        else:
            indices.add(int(part))
    valid = sorted(i for i in indices if 0 <= i < total_pages)
    if not valid:
        raise ValueError(
            f"Page range {spec!r} yields no valid pages for a {total_pages}-page document."
        )
    return valid


def extract_labels(
    doc: fitz.Document,
    min_font_size: float = 0.0,
    page_range: list[int] | None = None,
) -> list[Label]:
    """Extract all text spans from a PyMuPDF document as a list of :class:`Label` objects.

    Extraction uses ``page.get_text("dict")`` which returns the full block/line/span
    hierarchy with exact bbox, font metadata, and color for every glyph run.

    Spans are skipped when:
    - Their text is empty or whitespace-only.
    - Their bbox has effectively zero area.
    - Their font size is below ``min_font_size``.

    Args:
        doc: Open :class:`fitz.Document`.
        min_font_size: Discard spans smaller than this point size.
        page_range: Optional explicit list of 0-based page indices to process.
                    When None, all pages are processed.

    Returns:
        Ordered list of :class:`Label` objects (page order, then document order).
    """
    pages_to_process: list[int] = page_range if page_range is not None else list(range(len(doc)))
    labels: list[Label] = []

    for page_num in pages_to_process:
        page: fitz.Page = doc[page_num]
        rotation: int = page.rotation
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)  # type: ignore[arg-type]

        for bi, block in enumerate(text_dict.get("blocks", [])):
            # Only process text blocks (type 0); skip image blocks (type 1)
            if block.get("type") != 0:
                continue

            for li, line in enumerate(block.get("lines", [])):
                for si, span in enumerate(line.get("spans", [])):
                    text: str = span.get("text", "")

                    # Skip empty / whitespace-only spans
                    if not text or not text.strip():
                        logger.debug(
                            "Skipping whitespace span p%d b%d l%d s%d", page_num, bi, li, si
                        )
                        continue

                    raw_bbox: tuple[float, ...] = tuple(span["bbox"])
                    bbox = (raw_bbox[0], raw_bbox[1], raw_bbox[2], raw_bbox[3])

                    # Skip degenerate bboxes
                    if bbox_is_degenerate(bbox):
                        logger.debug(
                            "Skipping degenerate bbox span p%d b%d l%d s%d: %s",
                            page_num, bi, li, si, bbox,
                        )
                        continue

                    fontsize: float = float(span.get("size", 0.0))

                    # Skip spans below minimum font size
                    if fontsize < min_font_size:
                        logger.debug(
                            "Skipping small font (%.1f < %.1f) p%d b%d l%d s%d",
                            fontsize, min_font_size, page_num, bi, li, si,
                        )
                        continue

                    packed_color: int = span.get("color", 0)
                    raw_origin = span.get("origin")
                    if raw_origin is not None:
                        try:
                            origin = (float(raw_origin[0]), float(raw_origin[1]))
                        except Exception:
                            origin = None
                    else:
                        origin = None
                    label = Label(
                        id=f"p{page_num}_b{bi}_l{li}_s{si}",
                        page=page_num,
                        bbox=bbox,
                        original_text=text,
                        new_text=None,
                        fontname=span.get("font", "helv"),
                        fontsize=fontsize,
                        color=int_color_to_hex(packed_color),
                        flags=int(span.get("flags", 0)),
                        rotation=rotation,
                        origin=origin,
                        block_index=bi,
                        line_index=li,
                        span_index=si,
                    )
                    labels.append(label)

    logger.info("Extracted %d labels from %d pages.", len(labels), len(pages_to_process))
    return labels


def analyze_pdf(
    input_path: Path,
    output_path: Path,
    min_font_size: float = 0.0,
    page_range_spec: str | None = None,
    pretty: bool = True,
) -> int:
    """High-level entry point: open a PDF, extract labels, write JSON.

    Args:
        input_path: Path to the source PDF file.
        output_path: Destination path for the labels JSON file.
        min_font_size: Skip spans smaller than this (points).
        page_range_spec: Optional range string like '0-5' or '0,2,4'.
        pretty: Whether to indent the JSON output for human readability.

    Returns:
        Total number of labels written to the JSON file.

    Raises:
        FileNotFoundError: If ``input_path`` does not exist.
        ValueError: If ``page_range_spec`` is malformed.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc: fitz.Document = fitz.open(str(input_path))
    try:
        page_range: list[int] | None = None
        if page_range_spec:
            page_range = _parse_page_range(page_range_spec, len(doc))

        labels = extract_labels(doc, min_font_size=min_font_size, page_range=page_range)
    finally:
        doc.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(
            [label.model_dump() for label in labels],
            fh,
            indent=indent,
            ensure_ascii=False,
        )

    logger.info("Wrote %d labels to %s", len(labels), output_path)
    return len(labels)


def analyze_file(
    input_path: Path,
    output_path: Path,
    min_font_size: float = 0.0,
    page_range_spec: str | None = None,
    pretty: bool = True,
) -> int:
    """Analyze a PDF or Adobe Illustrator (.ai) file and write labels to JSON.

    Wraps :func:`analyze_pdf` with .ai file detection and compatibility warning.
    Adobe Illustrator files are opened via their embedded PDF compatibility layer.

    Args:
        input_path: Path to the input ``.pdf`` or ``.ai`` file.
        output_path: Destination path for the labels JSON file.
        min_font_size: Discard spans smaller than this point size.
        page_range_spec: Optional page range string (e.g. ``'0-5'``).
        pretty: Whether to pretty-print the JSON output.

    Returns:
        Total number of labels written to the JSON file.
    """
    file_type = detect_file_type(input_path)
    if file_type == "ai":
        logger.warning(AI_COMPAT_WARNING)
    return analyze_pdf(
        input_path=input_path,
        output_path=output_path,
        min_font_size=min_font_size,
        page_range_spec=page_range_spec,
        pretty=pretty,
    )
