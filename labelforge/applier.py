"""Apply edited labels back to a PDF using redact-then-insert."""

from __future__ import annotations

import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

from .models import Label
from .utils import (
    AI_COMPAT_WARNING,
    clamp_rect_to_page,
    detect_file_type,
    hex_color_to_rgb_float,
    resolve_font,
    resolve_font_file,
)

logger = logging.getLogger(__name__)


def load_labels(json_path: Path) -> list[Label]:
    """Parse and validate a labels JSON file produced by the analyzer.

    Args:
        json_path: Path to the labels JSON file.

    Returns:
        List of validated :class:`Label` objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON is malformed or fails Pydantic validation.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Labels file not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, list):
        raise ValueError("Labels JSON must be a top-level array.")

    labels: list[Label] = []
    errors: list[str] = []
    for i, item in enumerate(raw):
        try:
            labels.append(Label.model_validate(item))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"  Label[{i}]: {exc}")

    if errors:
        raise ValueError("Validation errors in labels JSON:\n" + "\n".join(errors))

    logger.info("Loaded %d labels from %s", len(labels), json_path)
    return labels


def _css_color(hex_str: str) -> str:
    """Convert #rrggbb to CSS rgb() string for insert_htmlbox."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgb({r},{g},{b})"


def _insert_htmlbox(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    label: "Label",
) -> None:
    """Insert text using insert_textbox with system font file and dynamic
    font-size shrink so text always fits within rect without overflowing.
    """
    font_key = resolve_font(label.fontname, label.flags)
    font_file = resolve_font_file(label.fontname, label.flags)
    color = hex_color_to_rgb_float(label.color)

    if font_file:
        font_kwargs: dict = {"fontfile": font_file, "fontname": label.fontname}
        _tmp = fitz.Font(fontfile=font_file)
        def _text_width(fs: float) -> float:
            return _tmp.text_length(text, fontsize=fs)
        def _orig_width(fs: float) -> float:
            return _tmp.text_length(label.original_text, fontsize=fs)
    else:
        font_kwargs = {"fontname": font_key}
        def _text_width(fs: float) -> float:
            return fitz.get_text_length(text, fontname=font_key, fontsize=fs)
        def _orig_width(fs: float) -> float:
            return fitz.get_text_length(label.original_text, fontname=font_key, fontsize=fs)

    # Use the original text's measured width as a baseline: if the original fit
    # the bbox at label.fontsize, the replacement should get the same budget.
    original_text_width = _orig_width(label.fontsize)
    effective_width = max(rect.width, original_text_width)

    # Shrink font size until text fits horizontally, respecting max_scale_down
    fontsize = label.fontsize
    min_fontsize = label.fontsize * label.max_scale_down
    while fontsize > min_fontsize and _text_width(fontsize) > effective_width:
        fontsize -= 0.25
    fontsize = max(fontsize, min_fontsize)

    if label.origin is not None:
        # Use the exact baseline origin for pixel-perfect vertical alignment.
        page.insert_text(
            fitz.Point(label.origin[0], label.origin[1]),
            text,
            fontsize=fontsize,
            color=color,
            **font_kwargs,
        )
        if fontsize < label.fontsize:
            logger.debug(
                "Label %s font shrunk %.2fpt → %.2fpt to fit",
                label.id, label.fontsize, fontsize,
            )
        return

    # No origin available — fall back to insert_textbox.
    min_h = fontsize * 1.5
    use_x1 = max(rect.x1, rect.x0 + effective_width)
    bbox_y1 = label.bbox[3]
    desired_y1 = max(rect.y1, rect.y0 + min_h)
    use_rect = fitz.Rect(rect.x0, rect.y0, use_x1, min(desired_y1, bbox_y1))

    result = page.insert_textbox(
        use_rect, text,
        fontsize=fontsize,
        color=color,
        align=fitz.TEXT_ALIGN_LEFT,
        **font_kwargs,
    )
    if result < 0:
        expanded = fitz.Rect(
            use_rect.x0, use_rect.y0,
            use_rect.x1, use_rect.y1 + abs(result) + fontsize,
        )
        result = page.insert_textbox(
            expanded, text,
            fontsize=fontsize,
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
            **font_kwargs,
        )
    if result < 0:
        logger.warning(
            "Text still overflows for label %s (result=%.1f) at fontsize=%.2f; "
            "using insert_text point fallback",
            label.id, result, fontsize,
        )
        page.insert_text(
            fitz.Point(use_rect.x0, use_rect.y0 + fontsize),
            text,
            fontsize=fontsize,
            color=color,
            **font_kwargs,
        )
    elif fontsize < label.fontsize:
        logger.debug(
            "Label %s font shrunk %.2fpt → %.2fpt to fit",
            label.id, label.fontsize, fontsize,
        )


def _insert_textbox_fallback(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    label: "Label",
) -> None:
    """Fallback: insert_textbox with dynamic font size shrink if needed."""
    font_key = resolve_font(label.fontname, label.flags)
    font_file = resolve_font_file(label.fontname, label.flags)
    color = hex_color_to_rgb_float(label.color)

    if font_file:
        font_kwargs: dict = {"fontfile": font_file, "fontname": label.fontname}
        _tmp_font = fitz.Font(fontfile=font_file)
        text_width = _tmp_font.text_length(text, fontsize=label.fontsize)
    else:
        font_kwargs = {"fontname": font_key}
        text_width = fitz.get_text_length(text, fontname=font_key, fontsize=label.fontsize)

    # Expand rect width if text is wider than the box
    use_rect = fitz.Rect(rect)
    min_w = max(use_rect.width, text_width + 1)
    min_h = max(use_rect.height, label.fontsize * 1.5)
    if min_w > use_rect.width or min_h > use_rect.height:
        use_rect = fitz.Rect(use_rect.x0, use_rect.y0, use_rect.x0 + min_w, use_rect.y0 + min_h)

    result = page.insert_textbox(
        use_rect, text,
        fontsize=label.fontsize,
        color=color,
        align=fitz.TEXT_ALIGN_LEFT,
        **font_kwargs,
    )
    if result < 0:
        expanded = fitz.Rect(
            use_rect.x0, use_rect.y0,
            use_rect.x1 + abs(text_width) + 2,
            use_rect.y1 + abs(result) + label.fontsize,
        )
        result2 = page.insert_textbox(
            expanded, text,
            fontsize=label.fontsize,
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
            **font_kwargs,
        )
        if result2 < 0:
            logger.warning(
                "Text overflow for label %s (result=%d); using insert_text point fallback",
                label.id, result,
            )
            page.insert_text(
                fitz.Point(rect.x0, rect.y0 + label.fontsize),
                text,
                fontsize=label.fontsize,
                color=color,
                **font_kwargs,
            )


def apply_labels(
    input_path: Path,
    labels: list[Label],
    output_path: Path,
    backup: bool = False,
    force: bool = False,
) -> int:
    """Apply edited labels to a PDF and save the result.

    For every label where ``new_text`` differs from ``original_text``:

    1. A white-fill redaction annotation is placed over the original bbox
       (slightly expanded to catch sub-pixel glyph bleed).
    2. ``page.apply_redactions()`` erases the underlying content.
    3. If ``new_text`` is non-empty, new text is inserted with the original
       font/size/color via ``page.insert_textbox()``.

    Pages are processed in a single pass: all redactions on a page are added
    first, then applied in one call, then all insertions are made. This avoids
    re-applying redactions multiple times and is more efficient.

    Args:
        input_path: Path to the original PDF.
        labels: Full list of labels (changed and unchanged).
        output_path: Destination path for the modified PDF.
        backup: If True, copy ``input_path`` to ``<input_path>.bak`` first.
        force: If True, overwrite ``output_path`` if it already exists.

    Returns:
        Number of labels that were actually changed.

    Raises:
        FileNotFoundError: If ``input_path`` does not exist.
        FileExistsError: If ``output_path`` exists and ``force`` is False.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    file_type = detect_file_type(input_path)
    if file_type == "ai":
        logger.warning(AI_COMPAT_WARNING)

    if output_path.exists() and not force:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --force to overwrite."
        )

    if backup:
        bak_path = input_path.with_suffix(input_path.suffix + ".bak")
        shutil.copy2(input_path, bak_path)
        logger.info("Backup written to %s", bak_path)

    # Group changed labels by page number for efficient processing
    changed_by_page: dict[int, list[Label]] = defaultdict(list)
    for label in labels:
        if label.is_changed:
            changed_by_page[label.page].append(label)

    total_changed = sum(len(v) for v in changed_by_page.values())
    if total_changed == 0:
        logger.info("No labels have new_text set — nothing to do.")
        # Still save a copy so the command always produces output
        shutil.copy2(input_path, output_path)
        return 0

    doc: fitz.Document = fitz.open(str(input_path))
    try:
        for page_num, page_labels in sorted(changed_by_page.items()):
            page: fitz.Page = doc[page_num]
            logger.debug("Processing page %d: %d changes", page_num, len(page_labels))

            # --- Phase 1: add all redaction annotations ---
            for label in page_labels:
                rect = fitz.Rect(label.bbox)
                rect = clamp_rect_to_page(rect, page)
                if rect.is_empty or rect.is_infinite:
                    logger.warning(
                        "Skipping degenerate rect for label %s after clamping", label.id
                    )
                    continue
                # fill=None: rely on content erasure only; no white rect painted
                # so adjacent vector border lines are not covered.
                page.add_redact_annot(rect, fill=None)

            # --- Phase 2: apply all redactions on this page at once ---
            # images=PDF_REDACT_IMAGE_NONE preserves images
            # graphics=PDF_REDACT_LINE_ART_NONE preserves vector paths/borders
            page.apply_redactions(  # type: ignore[attr-defined]
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            )

            # --- Phase 3: insert new text ---
            for label in page_labels:
                new_text = label.new_text
                if new_text is None or new_text == "":
                    # Erase-only: redaction already done, nothing to insert
                    continue

                # Apply padding but clamp so the rect keeps at least 4pt width/height
                raw = fitz.Rect(label.bbox)
                pad = min(
                    label.padding,
                    max(0.0, (raw.width - 4.0) / 2),
                    max(0.0, (raw.height - 4.0) / 2),
                )
                rect = fitz.Rect(
                    raw.x0 + pad, raw.y0 + pad,
                    raw.x1 - pad, raw.y1 - pad,
                )

                # Optional white-out: paint white over the redacted area before
                # inserting text. This catches any sub-pixel ink left behind.
                if label.white_out:
                    page.draw_rect(
                        fitz.Rect(label.bbox),
                        color=None,
                        fill=(1, 1, 1),
                        overlay=True,
                    )

                if label.auto_fit:
                    _insert_htmlbox(page, rect, new_text, label)
                else:
                    _insert_textbox_fallback(page, rect, new_text, label)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            expand=True,
        )
        logger.info("Saved modified PDF to %s (%d changes)", output_path, total_changed)
    finally:
        doc.close()

    return total_changed


def build_labels(
    labels: list[Label],
    output_path: Path,
    force: bool = False,
) -> int:
    """Create a new PDF from scratch using only labels JSON data.

    Places every label's text at its original bbox position on a blank white
    page. No source document is required. Background graphics, vectors, and
    images from the original are not included.

    Args:
        labels: List of :class:`Label` objects to render.
        output_path: Destination path for the generated PDF.
        force: If True, overwrite ``output_path`` if it already exists.

    Returns:
        Number of labels written.

    Raises:
        FileExistsError: If ``output_path`` exists and ``force`` is False.
        ValueError: If ``labels`` is empty.
    """
    if not labels:
        raise ValueError("No labels to build from — labels list is empty.")

    if output_path.exists() and not force:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --force to overwrite."
        )

    # Group labels by page
    by_page: dict[int, list[Label]] = defaultdict(list)
    for label in labels:
        by_page[label.page].append(label)

    # Determine page size from bboxes on each page (use max extents)
    doc: fitz.Document = fitz.open()
    try:
        for page_idx in sorted(by_page.keys()):
            page_labels = by_page[page_idx]
            x1 = max(lbl.bbox[2] for lbl in page_labels)
            y1 = max(lbl.bbox[3] for lbl in page_labels)
            # Add a small margin so text at edges is not clipped
            width = max(x1 + 20, 200)
            height = max(y1 + 20, 200)
            page = doc.new_page(width=width, height=height)

            for label in page_labels:
                text = label.new_text if label.new_text is not None else label.original_text
                if not text:
                    continue
                font_key = resolve_font(label.fontname, label.flags)
                color = hex_color_to_rgb_float(label.color)
                rect = fitz.Rect(label.bbox[0], label.bbox[1], label.bbox[2], label.bbox[3])
                result = page.insert_textbox(
                    rect,
                    text,
                    fontname=font_key,
                    fontsize=label.fontsize,
                    color=color,
                    align=0,
                )
                if result < 0:
                    page.insert_text(
                        fitz.Point(label.bbox[0], label.bbox[3]),
                        text,
                        fontname=font_key,
                        fontsize=label.fontsize,
                        color=color,
                    )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            expand=True,
        )
        logger.info("Built PDF with %d labels at %s", len(labels), output_path)
    finally:
        doc.close()

    return len(labels)
