"""Shape fill color modification using redact-and-redraw."""
from __future__ import annotations

import logging
from pathlib import Path

import fitz

from .utils import hex_color_to_rgb_float

logger = logging.getLogger(__name__)


def _replay_drawing_items(shape: fitz.Shape, items: list[dict]) -> None:
    """Replay serialized drawing items onto a fitz.Shape object."""
    for item in items:
        typ = item.get("type")
        if typ == "re":
            shape.draw_rect(fitz.Rect(*item["rect"]))
        elif typ == "l":
            shape.draw_line(fitz.Point(*item["p1"]), fitz.Point(*item["p2"]))
        elif typ == "c":
            shape.draw_curve(
                fitz.Point(*item["p1"]), fitz.Point(*item["p2"]),
                fitz.Point(*item["p3"]), fitz.Point(*item["p4"]),
            )


def _serialize_item(item) -> dict | None:
    """Convert a PyMuPDF drawing item tuple to a dict."""
    op = item[0]
    if op == "re":
        rect = item[1]
        return {"type": "re", "rect": [rect.x0, rect.y0, rect.x1, rect.y1]}
    elif op == "l":
        p1, p2 = item[1], item[2]
        return {"type": "l", "p1": [p1.x, p1.y], "p2": [p2.x, p2.y]}
    elif op == "c":
        p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
        return {"type": "c", "p1": [p1.x, p1.y], "p2": [p2.x, p2.y],
                "p3": [p3.x, p3.y], "p4": [p4.x, p4.y]}
    return None


def _overlaps(drawing: dict, target: fitz.Rect) -> bool:
    """Check if a drawing's rect overlaps with the target rect."""
    drect = drawing.get("rect")
    if drect is None:
        return False
    return fitz.Rect(drect).intersects(target)


def apply_shape_fill_change(
    input_path: Path,
    output_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    shape_drawings: list[dict] | None,
    new_fill_color: str,
    fill_opacity: float = 1.0,
    stroke_color: str | None = None,
    stroke_width: float | None = None,
) -> None:
    """Replace a shape's fill color using redact-then-redraw.

    Captures ALL vector drawings that overlap the shape bbox (including
    separate stroke-only paths), redacts the area, then replays every
    drawing — substituting only the fill color.

    Note: This removes overlapping text. The caller (applier) is responsible
    for re-inserting text components that overlap with shapes via the full
    font resolution pipeline.

    Args:
        input_path: Source PDF/AI file.
        output_path: Where to write the modified PDF.
        page_num: 0-based page index.
        bbox: (x0, y0, x1, y1) bounding box of the shape.
        shape_drawings: Pre-serialized drawing items (used as fallback).
        new_fill_color: New fill color as '#rrggbb' hex string.
        fill_opacity: Opacity for the new fill (0.0-1.0).
        stroke_color: Original stroke color (used as fallback).
        stroke_width: Original stroke width (used as fallback).
    """
    same_file = input_path.resolve() == output_path.resolve()
    save_path = output_path if not same_file else output_path.with_suffix(".tmp.pdf")

    doc = fitz.open(str(input_path))
    try:
        page = doc[page_num]
        target_rect = fitz.Rect(*bbox)

        # 1. Capture ALL vector drawings overlapping the target bbox
        all_drawings = page.get_drawings()
        overlapping = [d for d in all_drawings if _overlaps(d, target_rect)]

        # 2. Redact the area (removes all vector content + overlapping text)
        page.add_redact_annot(target_rect, fill=None)
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
        )

        # 3. Replay each overlapping drawing with updated fill
        new_fill = hex_color_to_rgb_float(new_fill_color)

        if overlapping:
            for drawing in overlapping:
                items = drawing.get("items", [])
                serialized = [_serialize_item(it) for it in items]
                serialized = [s for s in serialized if s is not None]
                if not serialized:
                    continue

                orig_fill = drawing.get("fill")
                orig_stroke = drawing.get("color")
                orig_width = drawing.get("width", 1)
                orig_opacity = drawing.get("fill_opacity", 1.0) or 1.0

                shape = fitz.Shape(page)
                _replay_drawing_items(shape, serialized)

                # If this drawing had a fill, use new color; otherwise keep no fill
                fill = new_fill if orig_fill is not None else None
                opacity = fill_opacity if orig_fill is not None else orig_opacity

                shape.finish(
                    fill=fill,
                    color=orig_stroke,  # preserve original stroke
                    fill_opacity=opacity,
                    width=orig_width if orig_width else None,
                    closePath=True,
                )
                shape.commit()
        elif shape_drawings:
            # Fallback: use pre-serialized items
            stroke = hex_color_to_rgb_float(stroke_color) if stroke_color else None
            width = stroke_width if stroke_width and stroke_width > 0 else None
            shape = fitz.Shape(page)
            _replay_drawing_items(shape, shape_drawings)
            shape.finish(
                fill=new_fill,
                color=stroke,
                fill_opacity=fill_opacity,
                width=width,
                closePath=True,
            )
            shape.commit()
        else:
            # Last resort: simple rectangle
            page.draw_rect(target_rect, color=None, fill=new_fill, fill_opacity=fill_opacity)

        doc.save(str(save_path), garbage=4, deflate=True)
        logger.info("Shape fill changed on page %d bbox %s to %s", page_num, bbox, new_fill_color)
    finally:
        doc.close()

    if same_file:
        save_path.replace(output_path)
