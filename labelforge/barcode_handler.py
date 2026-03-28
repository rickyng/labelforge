"""Barcode generation and PDF image replacement.

To add a new barcode format:
  1. Add the format to BarcodeFormat enum in component_models.py
  2. Handle the new format in generate_barcode_image() below
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF

from .component_models import BarcodeFormat

logger = logging.getLogger(__name__)

# Map BarcodeFormat -> python-barcode class name
_BARCODE_CLASS_MAP: dict[BarcodeFormat, str] = {
    BarcodeFormat.EAN13: "ean13",
    BarcodeFormat.EAN8: "ean8",
    BarcodeFormat.CODE128: "code128",
    BarcodeFormat.CODE39: "code39",
    BarcodeFormat.UPCA: "upca",
}


def generate_barcode_image(
    value: str,
    fmt: BarcodeFormat,
    size_px: tuple[int, int] | None = None,
) -> bytes:
    """Generate a barcode image and return it as PNG bytes.

    Args:
        value: The data to encode (e.g. "0123456789012" for EAN-13).
        fmt: The barcode format to use.
        size_px: Optional (width, height) to resize the output image.
                 If None, uses the library default size.

    Returns:
        PNG image bytes.

    Raises:
        ImportError: If required library (qrcode or python-barcode) is missing.
        ValueError: If the value is invalid for the chosen format.
    """
    from PIL import Image  # type: ignore[import]

    if fmt == BarcodeFormat.QR:
        import qrcode  # type: ignore[import]
        qr = qrcode.QRCode(border=1)
        qr.add_data(value)
        qr.make(fit=True)
        img: Image.Image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    else:
        import barcode as bc  # type: ignore[import]
        from barcode.writer import ImageWriter  # type: ignore[import]

        class_name = _BARCODE_CLASS_MAP.get(fmt)
        if class_name is None:
            raise ValueError(f"Unsupported barcode format: {fmt}")
        cls = bc.get_barcode_class(class_name)
        buf = io.BytesIO()
        # write_text=False suppresses the human-readable number printed below bars
        cls(value, writer=ImageWriter()).write(buf, options={
                "write_text": False,
                "quiet_zone": 1,
            })
        buf.seek(0)
        img = Image.open(buf).convert("RGB")

    if size_px is not None:
        # Autocrop whitespace so the bars fill the full target area
        from PIL import ImageChops
        bg = Image.new(img.mode, img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            img = img.crop(bbox)
        img = img.resize(size_px, Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def replace_component_image(
    doc: fitz.Document,
    page_num: int,
    bbox: tuple[float, float, float, float],
    new_image_bytes: bytes,
) -> None:
    """Replace the image at bbox on the given page with new_image_bytes.

    Strategy: redact (white-out) the original area, then insert the new image
    at the exact same bounding box so layout is preserved.

    Args:
        doc: Open fitz.Document (will be modified in place).
        page_num: 0-based page index.
        bbox: (x0, y0, x1, y1) in PDF points — the original image's position.
        new_image_bytes: PNG/JPEG bytes of the replacement image.
    """
    page = doc[page_num]
    rect = fitz.Rect(*bbox)

    # Redact the original image area with a white fill.
    # PDF_REDACT_LINE_ART_REMOVE is required to erase vector-drawn barcodes
    # (e.g. from .ai files) in addition to raster image content.
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_REMOVE,
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
    )

    # Insert the new image at the same position
    page.insert_image(rect, stream=new_image_bytes)
    logger.info("Replaced image on page %d at bbox %s", page_num, bbox)


def apply_barcode_replacement(
    input_path: Path,
    output_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    value: str,
    fmt: BarcodeFormat,
    size_px: tuple[int, int] | None = None,
) -> None:
    """High-level helper: generate barcode, replace in PDF, save to output_path.

    Args:
        input_path: Source PDF/AI file.
        output_path: Where to write the modified PDF.
        page_num: 0-based page index of the barcode component.
        bbox: Bounding box of the original barcode image in PDF points.
        value: New barcode value to encode.
        fmt: Barcode format.
        size_px: Optional pixel dimensions for the generated image.
    """
    new_image_bytes = generate_barcode_image(value, fmt, size_px)
    doc = fitz.open(str(input_path))
    try:
        replace_component_image(doc, page_num, bbox, new_image_bytes)
        doc.save(str(output_path), garbage=4, deflate=True)
        logger.info("Saved barcode-replaced PDF to %s", output_path)
    finally:
        doc.close()
