"""Pydantic v2 models for document component extraction.

Extend by adding new values to ComponentType and handling them in
document_analyzer.py and barcode_handler.py.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ComponentType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    BARCODE = "BARCODE"
    SHAPE = "SHAPE"


class BarcodeFormat(str, Enum):
    EAN13 = "ean13"
    EAN8 = "ean8"
    CODE128 = "code128"
    CODE39 = "code39"
    QR = "qr"
    UPCA = "upca"


class DocumentComponent(BaseModel):
    """A single extracted component from a PDF/AI document page."""

    id: str                                      # e.g. "p0_img_3", "p0_shape_1"
    type: ComponentType
    page: int                                    # 0-based page index
    bbox: tuple[float, float, float, float]      # x0, y0, x1, y1 in PDF points

    # PyMuPDF internal reference (images only)
    xref: int | None = None

    # TEXT fields
    text: str | None = None
    fontname: str | None = None
    fontsize: float | None = None
    color: str | None = None

    # IMAGE / BARCODE fields
    image_format: str | None = None             # "png", "jpeg", etc.
    width_px: int | None = None
    height_px: int | None = None
    thumbnail_b64: str | None = None            # base64-encoded PNG thumbnail

    # BARCODE-specific fields
    barcode_value: str | None = None
    barcode_format: BarcodeFormat | None = None

    # TEXT span provenance — needed for pixel-perfect apply
    flags: int | None = None        # font bitmask: bold=16, italic=2
    rotation: int | None = None     # page rotation in degrees
    origin: list[float] | None = None  # baseline origin [x, y]

    # Whether the component can be edited in the UI
    editable: bool = True


class ComponentsFile(BaseModel):
    """Top-level wrapper for components.json output."""

    source_file: str                     # absolute path to the original input file
    components: list[DocumentComponent]
