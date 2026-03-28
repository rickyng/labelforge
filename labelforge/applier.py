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
    extract_embedded_fonts,
    hex_color_to_rgb_float,
    resolve_font,
    resolve_font_file,
    strip_subset_prefix,
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


def _insert_htmlbox(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    label: "Label",
    embedded_fonts: dict[str, bytes] | None = None,
) -> None:
    """Insert text using insert_textbox with dynamic font-size shrink.

    Font resolution order:
    1. Embedded font extracted from the source document
    2. System font file from the hardcoded path table
    3. PyMuPDF built-in (Helvetica/Times/Courier family)
    """
    font_key = resolve_font(label.fontname, label.flags)
    font_file = resolve_font_file(label.fontname, label.flags)
    color = hex_color_to_rgb_float(label.color)

    embedded_bytes: bytes | None = None
    if embedded_fonts:
        lookup = strip_subset_prefix(label.fontname).lower()
        embedded_bytes = embedded_fonts.get(lookup)

    if embedded_bytes is not None:
        font_kwargs: dict = {"fontbuffer": embedded_bytes, "fontname": label.fontname}
        _tmp = fitz.Font(fontbuffer=embedded_bytes)
        def _text_width(fs: float) -> float:
            return _tmp.text_length(text, fontsize=fs)
        def _orig_width(fs: float) -> float:
            return _tmp.text_length(label.original_text, fontsize=fs)
    elif font_file:
        font_kwargs = {"fontfile": font_file, "fontname": label.fontname}
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
    embedded_fonts: dict[str, bytes] | None = None,
) -> None:
    """Fallback: insert_textbox with dynamic font size shrink if needed.

    Font resolution order:
    1. Embedded font extracted from the source document
    2. System font file from the hardcoded path table
    3. PyMuPDF built-in (Helvetica/Times/Courier family)
    """
    font_key = resolve_font(label.fontname, label.flags)
    font_file = resolve_font_file(label.fontname, label.flags)
    color = hex_color_to_rgb_float(label.color)

    embedded_bytes: bytes | None = None
    if embedded_fonts:
        lookup = strip_subset_prefix(label.fontname).lower()
        embedded_bytes = embedded_fonts.get(lookup)

    if embedded_bytes is not None:
        font_kwargs: dict = {"fontbuffer": embedded_bytes, "fontname": label.fontname}
        _tmp_font = fitz.Font(fontbuffer=embedded_bytes)
        text_width = _tmp_font.text_length(text, fontsize=label.fontsize)
    elif font_file:
        font_kwargs = {"fontfile": font_file, "fontname": label.fontname}
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
        embedded_fonts = extract_embedded_fonts(doc)
        if embedded_fonts:
            logger.info("Reusing %d embedded font(s) from source document", len(embedded_fonts))

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
                    _insert_htmlbox(page, rect, new_text, label, embedded_fonts)
                else:
                    _insert_textbox_fallback(page, rect, new_text, label, embedded_fonts)

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


def apply_from_components(
    components_path: Path,
    changes_path: Path,
    output_path: Path,
    force: bool = False,
) -> int:
    """Apply changes to a document using components.json + changes.json.

    The source file path is embedded in components.json so no separate
    input file argument is needed.

    Args:
        components_path: Path to components.json from ``labelforge components``.
        changes_path: Path to changes.json — a ``{component_id: new_value}`` map.
        output_path: Destination path for the modified PDF.
        force: If True, overwrite ``output_path`` if it already exists.

    Returns:
        Number of components actually changed.
    """
    from .component_models import ComponentsFile, ComponentType, BarcodeFormat as BFmt
    from .barcode_handler import apply_barcode_replacement

    with components_path.open("r", encoding="utf-8") as fh:
        cf = ComponentsFile.model_validate(json.load(fh))
    input_path = Path(cf.source_file)

    with changes_path.open("r", encoding="utf-8") as fh:
        changes: dict[str, str] = json.load(fh)

    if not changes:
        logger.info("No changes in changes.json — nothing to do.")
        shutil.copy2(input_path, output_path)
        return 0

    comp_by_id = {c.id: c for c in cf.components}
    text_labels: list[Label] = []
    barcode_jobs: list[tuple] = []

    for cid, new_value in changes.items():
        comp = comp_by_id.get(cid)
        if comp is None:
            logger.warning("Unknown component id in changes.json: %s — skipped", cid)
            continue
        if comp.type == ComponentType.TEXT:
            text_labels.append(Label(
                id=comp.id,
                page=comp.page,
                bbox=comp.bbox,
                original_text=comp.text or "",
                new_text=new_value,
                fontname=comp.fontname or "helv",
                fontsize=comp.fontsize or 10.0,
                color=comp.color or "#000000",
                flags=comp.flags or 0,
                rotation=comp.rotation or 0,
                origin=comp.origin,
            ))
        elif comp.type == ComponentType.BARCODE:
            barcode_jobs.append((comp, new_value))
        else:
            logger.warning("Component %s type %s is not editable — skipped", cid, comp.type)

    changed = 0
    current_input = input_path

    if text_labels:
        changed += apply_labels(
            input_path=current_input,
            labels=text_labels,
            output_path=output_path,
            force=force,
        )
        current_input = output_path

    for comp, new_value in barcode_jobs:
        if not comp.barcode_format:
            logger.warning("Barcode component %s has no barcode_format — skipped", comp.id)
            continue
        try:
            fmt = BFmt(comp.barcode_format)
        except ValueError:
            logger.warning("Unknown barcode format %s for component %s — skipped", comp.barcode_format, comp.id)
            continue
        size_px: tuple[int, int] | None = None
        if comp.width_px and comp.height_px:
            size_px = (comp.width_px, comp.height_px)
        else:
            w_pt = comp.bbox[2] - comp.bbox[0]
            h_pt = comp.bbox[3] - comp.bbox[1]
            if w_pt > 0 and h_pt > 0:
                size_px = (max(1, round(w_pt * 150 / 72)), max(1, round(h_pt * 150 / 72)))
        apply_barcode_replacement(
            input_path=current_input,
            output_path=output_path,
            page_num=comp.page,
            bbox=comp.bbox,
            value=new_value,
            fmt=fmt,
            size_px=size_px,
        )
        current_input = output_path
        changed += 1

    if not text_labels and not barcode_jobs:
        shutil.copy2(input_path, output_path)

    return changed


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
