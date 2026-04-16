"""Full document component extractor for PDF/AI files.

Extracts TEXT, IMAGE, BARCODE, and SHAPE components from every page
using PyMuPDF. Barcode detection uses pyzbar (optional — gracefully
degraded if libzbar is not installed).

To add a new component type:
  1. Add the type to ComponentType in component_models.py
  2. Add an _extract_<type>_components() function here
  3. Call it from extract_components()
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import fitz  # PyMuPDF

from .component_models import BarcodeFormat, ComponentType, ComponentsFile, DocumentComponent

logger = logging.getLogger(__name__)

# Map pyzbar type strings -> BarcodeFormat enum
_ZBAR_TYPE_MAP: dict[str, BarcodeFormat] = {
    "EAN13": BarcodeFormat.EAN13,
    "EAN8": BarcodeFormat.EAN8,
    "CODE128": BarcodeFormat.CODE128,
    "CODE39": BarcodeFormat.CODE39,
    "QRCODE": BarcodeFormat.QR,
    "UPCA": BarcodeFormat.UPCA,
}

def _try_decode_barcode(image_bytes: bytes) -> tuple[str | None, BarcodeFormat | None]:
    """Attempt to decode a barcode from raw image bytes using pyzbar.

    Returns (value, format) on success, (None, None) if no barcode found
    or if pyzbar / libzbar is not installed.
    """
    try:
        from pyzbar.pyzbar import decode  # type: ignore[import]
        from PIL import Image

        pil = Image.open(io.BytesIO(image_bytes))
        results = decode(pil)
        if results:
            r = results[0]
            fmt = _ZBAR_TYPE_MAP.get(r.type.name if hasattr(r.type, "name") else str(r.type))
            value = r.data.decode("utf-8", errors="replace")
            logger.info("Barcode detected: %s (%s)", value, fmt)
            return value, fmt
    except ImportError:
        logger.warning("pyzbar not installed — barcode detection skipped. Install with: pip install pyzbar")
    except Exception as exc:
        logger.warning("Barcode decode failed: %s", exc)
    return None, None


def _make_thumbnail_b64(image_bytes: bytes, max_px: int = 150) -> str | None:
    """Resize image to a thumbnail and return as a base64 PNG string."""
    try:
        from PIL import Image
        pil = Image.open(io.BytesIO(image_bytes))
        pil.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return None


def _extract_text_components(
    page: fitz.Page,
    page_num: int,
    out: list[DocumentComponent],
) -> None:
    """Extract text spans from a page using get_text('dict')."""
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES).get("blocks", [])
    for b_idx, block in enumerate(blocks):
        if block.get("type") != 0:  # 0 = text block
            continue
        for l_idx, line in enumerate(block.get("lines", [])):
            for s_idx, span in enumerate(line.get("spans", [])):
                text = span.get("text", "").strip()
                if not text:
                    continue
                bbox = span.get("bbox", (0, 0, 0, 0))
                color_int = span.get("color", 0)
                hex_color = f"#{color_int:06x}"
                origin = span.get("origin")
                out.append(DocumentComponent(
                    id=f"p{page_num}_t_b{b_idx}_l{l_idx}_s{s_idx}",
                    type=ComponentType.TEXT,
                    page=page_num,
                    bbox=tuple(bbox),  # type: ignore[arg-type]
                    text=span.get("text", ""),
                    fontname=span.get("font", ""),
                    fontsize=float(span.get("size", 0)),
                    color=hex_color,
                    flags=span.get("flags"),
                    rotation=page.rotation,
                    origin=list(origin) if origin else None,
                    editable=True,
                ))


def _extract_image_components(
    doc: fitz.Document,
    page: fitz.Page,
    page_num: int,
    out: list[DocumentComponent],
) -> None:
    """Extract embedded images (and detect barcodes within them)."""
    for idx, img_info in enumerate(page.get_images(full=True)):
        xref = img_info[0]
        try:
            bbox_rect = page.get_image_bbox(img_info)
        except Exception:
            continue
        try:
            base_image = doc.extract_image(xref)
        except Exception as exc:
            logger.warning("Could not extract image xref=%d: %s", xref, exc)
            continue

        image_bytes = base_image["image"]
        ext = base_image.get("ext", "png")

        barcode_value, barcode_fmt = _try_decode_barcode(image_bytes)
        comp_type = ComponentType.BARCODE if barcode_value else ComponentType.IMAGE
        thumbnail = _make_thumbnail_b64(image_bytes)

        width_px: int | None = None
        height_px: int | None = None
        try:
            from PIL import Image as PilImage
            pil = PilImage.open(io.BytesIO(image_bytes))
            width_px, height_px = pil.size
        except Exception:
            pass

        out.append(DocumentComponent(
            id=f"p{page_num}_img_{idx}",
            type=comp_type,
            page=page_num,
            bbox=(bbox_rect.x0, bbox_rect.y0, bbox_rect.x1, bbox_rect.y1),
            xref=xref,
            image_format=ext,
            width_px=width_px,
            height_px=height_px,
            thumbnail_b64=thumbnail,
            barcode_value=barcode_value,
            barcode_format=barcode_fmt,
            editable=True,
        ))


def _scan_page_for_vector_barcodes(
    page: fitz.Page,
    page_num: int,
    out: list[DocumentComponent],
    dpi: int = 150,
) -> None:
    """Render the page to a bitmap and scan for barcodes using pyzbar.

    This catches vector-drawn barcodes (e.g. from .ai files) that have no
    embedded raster image and are therefore invisible to get_images().
    Each detected barcode is added as a BARCODE component with bbox mapped
    back to PDF point space.
    """
    try:
        from pyzbar.pyzbar import decode  # type: ignore[import]
        from PIL import Image
    except ImportError:
        logger.warning("pyzbar not installed — vector barcode scan skipped.")
        return

    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pil = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        results = decode(pil)
    except Exception as exc:
        logger.warning("Page raster scan failed: %s", exc)
        return

    if not results:
        return

    scale = 72 / dpi  # pixel -> PDF point
    page_rect = page.rect

    for idx, r in enumerate(results):
        fmt = _ZBAR_TYPE_MAP.get(r.type.name if hasattr(r.type, "name") else str(r.type))
        value = r.data.decode("utf-8", errors="replace")
        lft = r.rect.left * scale
        top = r.rect.top * scale
        rgt = r.rect.left * scale + r.rect.width * scale
        bot = r.rect.top * scale + r.rect.height * scale
        # Clamp to page bounds
        lft = max(lft, page_rect.x0)
        top = max(top, page_rect.y0)
        rgt = min(rgt, page_rect.x1)
        bot = min(bot, page_rect.y1)

        # Crop thumbnail from the pixmap region
        crop_box = (r.rect.left, r.rect.top, r.rect.left + r.rect.width, r.rect.top + r.rect.height)
        thumb_b64: str | None = None
        try:
            cropped = pil.crop(crop_box)
            buf = io.BytesIO()
            cropped.thumbnail((150, 150))
            cropped.save(buf, format="PNG")
            thumb_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            pass

        logger.info("Vector barcode detected on page %d: %s (%s)", page_num, value, fmt)
        out.append(DocumentComponent(
            id=f"p{page_num}_vbarcode_{idx}",
            type=ComponentType.BARCODE,
            page=page_num,
            bbox=(lft, top, rgt, bot),
            barcode_value=value,
            barcode_format=fmt,
            thumbnail_b64=thumb_b64,
            editable=True,
        ))


def _rgb_float_to_hex(rgb: tuple[float, float, float] | None) -> str | None:
    """Convert PyMuPDF (r, g, b) floats in [0, 1] to '#rrggbb' hex string."""
    if rgb is None:
        return None
    r, g, b = rgb
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _calculate_block_bboxes(
    components: list[DocumentComponent],
) -> dict[int, tuple[float, float, float, float]]:
    """Calculate bounding box for each PyMuPDF block (union of all spans in block).

    Returns a dict mapping block index -> union bounding box tuple (x0, y0, x1, y1).
    """
    block_bboxes: dict[int, tuple[float, float, float, float]] = {}

    for comp in components:
        if comp.type != ComponentType.TEXT:
            continue

        # Parse component ID: p{page}_t_b{block}_l{line}_s{span}
        parts = comp.id.split("_")
        if len(parts) < 5 or not parts[0].startswith("p"):
            continue

        try:
            block_idx = int(parts[2][1:])  # b3 -> 3
        except (IndexError, ValueError):
            continue

        if block_idx not in block_bboxes:
            block_bboxes[block_idx] = comp.bbox
        else:
            # Union with existing bbox
            existing = block_bboxes[block_idx]
            block_bboxes[block_idx] = (
                min(existing[0], comp.bbox[0]),
                min(existing[1], comp.bbox[1]),
                max(existing[2], comp.bbox[2]),
                max(existing[3], comp.bbox[3]),
            )

    return block_bboxes


def _merge_adjacent_blocks(
    components: list[DocumentComponent],
    threshold: float = 3.0,
) -> dict[int, int]:
    """Find blocks to merge based on spatial proximity.

    Uses union-find (disjoint set) to handle transitive merging chains.
    Returns a dict mapping original block index -> merged block index.

    Blocks are merged if they are within `threshold` distance and either:
    - Vertically adjacent with horizontal overlap (same column, close lines)
    - Horizontally adjacent with vertical overlap (same row, close columns)
    """
    # Union-find implementation
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Calculate block bboxes
    block_bboxes = _calculate_block_bboxes(components)
    if not block_bboxes:
        return {}

    # Sort block indices by vertical position (top y-coordinate)
    sorted_blocks = sorted(block_bboxes.keys(), key=lambda b: block_bboxes[b][1])

    # Check adjacent pairs for proximity
    for i in range(len(sorted_blocks) - 1):
        b1, b2 = sorted_blocks[i], sorted_blocks[i + 1]
        bbox1, bbox2 = block_bboxes[b1], block_bboxes[b2]

        # Check vertical gap (b2 is below b1)
        vertical_gap = bbox2[1] - bbox1[3]  # top of b2 - bottom of b1
        # Check horizontal overlap
        horizontal_overlap = not (bbox1[2] < bbox2[0] or bbox2[2] < bbox1[0])

        if 0 <= vertical_gap <= threshold and horizontal_overlap:
            union(b1, b2)
            continue

        # Check horizontal gap (blocks side by side)
        horizontal_gap = min(abs(bbox1[2] - bbox2[0]), abs(bbox2[2] - bbox1[0]))
        vertical_overlap = not (bbox1[3] < bbox2[1] or bbox2[3] < bbox1[1])

        if 0 <= horizontal_gap <= threshold and vertical_overlap:
            union(b1, b2)

    # Build mapping: original block -> canonical merged block
    return {b: find(b) for b in block_bboxes.keys()}


def _serialize_drawing_item(item) -> dict | None:
    """Convert a PyMuPDF drawing item tuple to a JSON-serializable dict."""
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


def _extract_shape_components(
    page: fitz.Page,
    page_num: int,
    out: list[DocumentComponent],
) -> None:
    """Extract vector shapes including fill color and path items for redraw."""
    drawings = page.get_drawings()
    for idx, drawing in enumerate(drawings):
        rect = drawing.get("rect")
        if rect is None:
            continue

        fill = drawing.get("fill")
        fill_opacity = drawing.get("fill_opacity")
        stroke = drawing.get("color")  # stroke color
        line_width = drawing.get("width", 0)  # stroke width

        # Serialize drawing items for accurate redraw during apply
        items = drawing.get("items", [])
        serialized = [s for s in (_serialize_drawing_item(it) for it in items) if s is not None]

        has_fill = fill is not None

        out.append(DocumentComponent(
            id=f"p{page_num}_shape_{idx}",
            type=ComponentType.SHAPE,
            page=page_num,
            bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
            fill_color=_rgb_float_to_hex(fill),
            fill_opacity=fill_opacity if fill_opacity is not None else 1.0,
            stroke_color=_rgb_float_to_hex(stroke),
            stroke_width=line_width if line_width else None,
            shape_drawings=serialized if has_fill else None,
            editable=has_fill,
        ))


def _ocr_shape_components(
    page: fitz.Page,
    page_num: int,
    components: list[DocumentComponent],
    ocr_zones: dict[str, tuple[float, float, float, float]] | None = None,
    languages: list[str] | None = None,
    confidence_threshold: float = 0.5,
) -> None:
    """Run OCR on SHAPE components that fall within defined zones.

    Modifies components in-place, populating ``ocr_text``, ``ocr_confidence``,
    and ``ocr_language`` on matching SHAPE components.

    Args:
        page: PyMuPDF Page object.
        page_num: 0-based page index.
        components: List of already-extracted components (mutated in place).
        ocr_zones: Mapping of zone_name → (x0, y0, x1, y1) in PDF points.
            If *None*, OCR runs on **all** shape components.
        languages: EasyOCR language codes (default: ``["ch_sim", "en", "ko"]``).
        confidence_threshold: Minimum confidence to store OCR result.
    """
    from .ocr_handler import ocr_shape_region

    # Collect SHAPE components for this page
    shape_comps = [
        c for c in components
        if c.type == ComponentType.SHAPE and c.page == page_num
    ]

    if not shape_comps:
        return

    for comp in shape_comps:
        # If zones are defined, only OCR shapes that overlap a zone
        if ocr_zones:
            matched = False
            for zone_bbox in ocr_zones.values():
                zr = fitz.Rect(zone_bbox)
                cr = fitz.Rect(comp.bbox)
                if not (zr & cr).is_empty:
                    matched = True
                    break
            if not matched:
                continue

        text, confidence, lang = ocr_shape_region(
            page, comp.bbox, dpi=150, languages=languages,
        )

        if text and confidence >= confidence_threshold:
            comp.ocr_text = text
            comp.ocr_confidence = confidence
            comp.ocr_language = lang
            logger.info(
                "OCR on shape %s: '%s' (%.2f)",
                comp.id, text, confidence,
            )


def extract_components(
    doc: fitz.Document,
    enable_ocr: bool = False,
    ocr_zones: dict[str, tuple[float, float, float, float]] | None = None,
    ocr_languages: list[str] | None = None,
) -> list[DocumentComponent]:
    """Extract all components from every page of a PyMuPDF document.

    Returns a flat list of DocumentComponent objects ordered by page.

    Args:
        doc: PyMuPDF Document.
        enable_ocr: If True, run OCR on SHAPE components in defined zones.
        ocr_zones: Zone bboxes for OCR (mapping_name → {zone_name → bbox}).
        ocr_languages: EasyOCR language codes for OCR.
    """
    components: list[DocumentComponent] = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        _extract_text_components(page, page_num, components)
        _extract_image_components(doc, page, page_num, components)
        _scan_page_for_vector_barcodes(page, page_num, components)
        _extract_shape_components(page, page_num, components)

        if enable_ocr:
            _ocr_shape_components(
                page, page_num, components,
                ocr_zones=ocr_zones,
                languages=ocr_languages,
            )

        logger.info(
            "Page %d: extracted %d components so far",
            page_num,
            len(components),
        )
    return components


def extract_components_from_path(
    input_path: Path,
    enable_ocr: bool = False,
    ocr_zones: dict[str, tuple[float, float, float, float]] | None = None,
    ocr_languages: list[str] | None = None,
) -> ComponentsFile:
    """Convenience wrapper: open a PDF/AI file and extract all components.

    Returns a ComponentsFile that embeds the absolute source path so that
    `labelforge apply --components` needs no separate input file argument.

    Args:
        input_path: Path to the PDF or AI file.
        enable_ocr: If True, run OCR on SHAPE components in defined zones.
        ocr_zones: Zone bboxes for OCR (zone_name → bbox tuple).
        ocr_languages: EasyOCR language codes.
    """
    doc = fitz.open(str(input_path))
    try:
        components = extract_components(
            doc,
            enable_ocr=enable_ocr,
            ocr_zones=ocr_zones,
            ocr_languages=ocr_languages,
        )
    finally:
        doc.close()
    return ComponentsFile(
        source_file=str(input_path.resolve()),
        components=components,
    )


from typing import Literal


def group_text_components(
    components: list[DocumentComponent],
    mode: Literal["span", "line", "block"] = "span",
    proximity_threshold: float = 0.0,
) -> list[DocumentComponent]:
    """Group TEXT components by the specified granularity.

    Args:
        components: List of DocumentComponent objects (span-level)
        mode: Grouping mode
            - "span": no grouping, return as-is
            - "line": group by (page, block, line) → p{page}_t_b{block}_l{line}
            - "block": group by (page, block) → p{page}_t_b{block}
        proximity_threshold: If > 0, merge spatially adjacent blocks within this
            distance (in PDF points) before structural grouping. Helps combine
            text that PyMuPDF split into multiple blocks.

    Returns:
        New list with TEXT components grouped, non-TEXT unchanged.
    """
    if mode == "span":
        return components

    # Step 1: Apply proximity merging if threshold > 0
    if proximity_threshold > 0 and mode in ("line", "block"):
        block_merge_map = _merge_adjacent_blocks(components, proximity_threshold)
        # Update component IDs with merged block index
        for comp in components:
            if comp.type != ComponentType.TEXT:
                continue
            parts = comp.id.split("_")
            if len(parts) >= 5 and parts[2].startswith("b"):
                try:
                    orig_block = int(parts[2][1:])
                    merged_block = block_merge_map.get(orig_block, orig_block)
                    parts[2] = f"b{merged_block}"
                    # Create new component with updated ID
                    # Note: We mutate the ID directly since components may be reused
                    comp.id = "_".join(parts)
                except (IndexError, ValueError):
                    continue

    # Step 2: Separate TEXT from non-TEXT components
    text_comps = [c for c in components if c.type == ComponentType.TEXT]
    non_text_comps = [c for c in components if c.type != ComponentType.TEXT]

    if not text_comps:
        return components

    # Build grouping key -> list of components
    from collections import defaultdict

    grouped: dict[tuple, list[DocumentComponent]] = defaultdict(list)

    for comp in text_comps:
        # Parse component ID: p{page}_t_b{block}_l{line}_s{span}
        parts = comp.id.split("_")
        if len(parts) < 5 or not parts[0].startswith("p"):
            # Unknown format, treat as its own group
            key = (comp.page, comp.id)
            grouped[key].append(comp)
            continue

        try:
            page_num = int(parts[0][1:])  # p0 -> 0
            block_num = int(parts[2][1:])  # b4 -> 4

            if mode == "line":
                line_num = int(parts[4][1:])  # l7 -> 7
                key = (page_num, block_num, line_num)
            else:  # block
                key = (page_num, block_num)

            grouped[key].append(comp)
        except (IndexError, ValueError):
            # Parsing failed, keep as individual
            key = (comp.page, comp.id)
            grouped[key].append(comp)

    # Merge each group into a single component
    result_components: list[DocumentComponent] = list(non_text_comps)

    # Sort keys for consistent ordering
    sorted_keys = sorted(grouped.keys(), key=lambda k: (k[0] if len(k) >= 1 else 0,
                                                        k[1] if len(k) >= 2 else 0,
                                                        k[2] if len(k) >= 3 else 0))

    for key in sorted_keys:
        group = grouped[key]

        if len(group) == 1:
            # Single component, just update ID if needed
            comp = group[0]
            if mode == "line":
                # Change ID from p{page}_t_b{block}_l{line}_s{span} to p{page}_t_b{block}_l{line}
                new_id = f"p{comp.page}_t_b{key[1]}_l{key[2]}"
            else:  # block
                new_id = f"p{comp.page}_t_b{key[1]}"
            result_components.append(DocumentComponent(
                id=new_id,
                type=comp.type,
                page=comp.page,
                bbox=comp.bbox,
                text=comp.text,
                fontname=comp.fontname,
                fontsize=comp.fontsize,
                color=comp.color,
                flags=comp.flags,
                rotation=comp.rotation,
                origin=comp.origin,
                editable=comp.editable,
            ))
        else:
            # Multiple spans in group - merge them
            # Union bbox
            min_x = min(c.bbox[0] for c in group)
            min_y = min(c.bbox[1] for c in group)
            max_x = max(c.bbox[2] for c in group)
            max_y = max(c.bbox[3] for c in group)

            # Concatenate text (sorted by span index within line/block)
            # Group was built from original component order, sort by span index
            sorted_group = sorted(group, key=lambda c: c.id)

            # For line mode, spans are already ordered left-to-right in the PDF
            # For block mode, we need to sort by x position
            if mode == "block":
                sorted_group = sorted(group, key=lambda c: c.bbox[0])

            # Combine text with space separation
            combined_text = " ".join(c.text.strip() for c in sorted_group if c.text)

            # Use first span's properties
            first = sorted_group[0]

            if mode == "line":
                new_id = f"p{first.page}_t_b{key[1]}_l{key[2]}"
            else:  # block
                new_id = f"p{first.page}_t_b{key[1]}"

            result_components.append(DocumentComponent(
                id=new_id,
                type=ComponentType.TEXT,
                page=first.page,
                bbox=(min_x, min_y, max_x, max_y),
                text=combined_text,
                fontname=first.fontname,
                fontsize=first.fontsize,
                color=first.color,
                flags=first.flags,
                rotation=first.rotation,
                origin=first.origin,
                editable=first.editable,
            ))

    # Sort result by page, then by bbox (top-to-bottom, left-to-right)
    result_components.sort(key=lambda c: (c.page, c.bbox[1], c.bbox[0]))

    return result_components




