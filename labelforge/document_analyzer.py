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
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
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


def _extract_shape_components(
    page: fitz.Page,
    page_num: int,
    out: list[DocumentComponent],
) -> None:
    """Extract basic vector shapes/paths (view-only)."""
    drawings = page.get_drawings()
    for idx, drawing in enumerate(drawings):
        rect = drawing.get("rect")
        if rect is None:
            continue
        out.append(DocumentComponent(
            id=f"p{page_num}_shape_{idx}",
            type=ComponentType.SHAPE,
            page=page_num,
            bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
            editable=False,  # shapes are view-only for now
        ))


def extract_components(doc: fitz.Document) -> list[DocumentComponent]:
    """Extract all components from every page of a PyMuPDF document.

    Returns a flat list of DocumentComponent objects ordered by page.
    """
    components: list[DocumentComponent] = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        _extract_text_components(page, page_num, components)
        _extract_image_components(doc, page, page_num, components)
        _scan_page_for_vector_barcodes(page, page_num, components)
        _extract_shape_components(page, page_num, components)
        logger.info(
            "Page %d: extracted %d components so far",
            page_num,
            len(components),
        )
    return components


def extract_components_from_path(input_path: Path) -> ComponentsFile:
    """Convenience wrapper: open a PDF/AI file and extract all components.

    Returns a ComponentsFile that embeds the absolute source path so that
    `labelforge apply --components` needs no separate input file argument.
    """
    doc = fitz.open(str(input_path))
    try:
        components = extract_components(doc)
    finally:
        doc.close()
    return ComponentsFile(
        source_file=str(input_path.resolve()),
        components=components,
    )




