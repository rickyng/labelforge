"""Utility helpers for color conversion, font resolution, bbox manipulation, and file type detection."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font resolution
# ---------------------------------------------------------------------------

# Maps common PDF font name fragments → PyMuPDF built-in font keys.
# PyMuPDF built-ins: helv, tiro, cour, hebo, heit, hebi, tibo, tiit, tibi, cobo, coit, cobi, symb, zadb
_FONT_MAP: dict[str, str] = {
    "helvetica": "helv",
    "helv": "helv",
    "arial": "helv",
    "times": "tiro",
    "tiro": "tiro",
    "courier": "cour",
    "cour": "cour",
    "symbol": "symb",
    "zapfdingbats": "zadb",
    "zapf": "zadb",
}

# Maps font name fragments to system font file paths (macOS + common Linux paths).
# Keys are lowercase fragments; values are candidate paths in priority order.
_SYSTEM_FONT_PATHS: list[tuple[str, list[str]]] = [
    ("arial-black", [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Black.ttf",
    ]),
    ("arial-bolditalic", [
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold_Italic.ttf",
    ]),
    ("arial-bold", [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    ]),
    ("arial-italic", [
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Italic.ttf",
    ]),
    ("arialmt", [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    ]),
    ("arial", [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    ]),
    ("times new roman", [
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf",
    ]),
    ("courier new", [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Courier_New.ttf",
    ]),
]


def resolve_font_file(fontname: str, flags: int = 0) -> str | None:
    """Try to find a system font file matching the given PDF font name.

    Checks known system font paths for macOS and common Linux distributions.
    Returns the path to the first existing font file found, or None if no
    system font is available (caller should fall back to built-in fonts).

    Args:
        fontname: Font name string from the PDF span.
        flags: PyMuPDF font flags bitmask (bold=16, italic=2).

    Returns:
        Absolute path string to a font file, or ``None``.
    """
    base = strip_subset_prefix(fontname).lower().replace(" ", "-")
    bold = bool(flags & 16) or "bold" in base
    italic = bool(flags & 2) or "italic" in base or "oblique" in base

    # Build candidate key based on bold/italic flags
    if bold and italic:
        variant = base + "-bolditalic"
    elif bold:
        variant = base + "-bold"
    elif italic:
        variant = base + "-italic"
    else:
        variant = base

    for fragment, paths in _SYSTEM_FONT_PATHS:
        if fragment in variant or fragment in base:
            for p in paths:
                if Path(p).exists():
                    return p
    return None

_SUBSET_RE = re.compile(r"^[A-Z]{6}\+")


def strip_subset_prefix(fontname: str) -> str:
    """Remove PDF subset prefix like 'ABCDEF+' from a font name."""
    return _SUBSET_RE.sub("", fontname)


def resolve_font(fontname: str, flags: int = 0) -> str:
    """Map a PDF font name to a PyMuPDF built-in font key.

    Resolution order:
    1. Strip subset prefix (``ABCDEF+FontName`` → ``FontName``)
    2. Try lowercase fragment match against known font map
    3. Apply bold/italic flags to choose the right variant
    4. Fall back to ``helv`` (Helvetica)

    Args:
        fontname: Font name string from the PDF span.
        flags: PyMuPDF font flags bitmask (bold=16, italic=2).

    Returns:
        A valid PyMuPDF built-in font key string.
    """
    bold = bool(flags & 16)
    italic = bool(flags & 2)

    base = strip_subset_prefix(fontname).lower()

    # Detect bold/italic from font name if not in flags
    if "bold" in base:
        bold = True
    if "italic" in base or "oblique" in base:
        italic = True

    # Find base family
    family = "helv"  # default
    for fragment, key in _FONT_MAP.items():
        if fragment in base:
            family = key
            break

    # Apply variant
    if family == "helv":
        if bold and italic:
            return "hebi"
        if bold:
            return "hebo"
        if italic:
            return "heit"
        return "helv"
    if family == "tiro":
        if bold and italic:
            return "tibi"
        if bold:
            return "tibo"
        if italic:
            return "tiit"
        return "tiro"
    if family == "cour":
        if bold and italic:
            return "cobi"
        if bold:
            return "cobo"
        if italic:
            return "coit"
        return "cour"

    # symb / zadb have no variants
    return family


# ---------------------------------------------------------------------------
# Color conversion
# ---------------------------------------------------------------------------


def int_color_to_hex(packed: int) -> str:
    """Convert a packed RGB integer (from PyMuPDF span) to ``#rrggbb`` string.

    PyMuPDF encodes color as ``(r << 16) | (g << 8) | b`` where each channel
    is 0–255. Negative values (rare, from malformed PDFs) are clamped to 0.

    Args:
        packed: Packed integer color value.

    Returns:
        Lower-case CSS hex color string.
    """
    return f"#{max(0, packed) & 0xFFFFFF:06x}"


def hex_color_to_rgb_float(hex_str: str) -> tuple[float, float, float]:
    """Convert ``#rrggbb`` to a float RGB tuple in [0.0, 1.0] range.

    Required by PyMuPDF's ``insert_textbox`` / ``insert_text`` ``color`` param.

    Args:
        hex_str: CSS hex color string like ``#1a2b3c``.

    Returns:
        ``(r, g, b)`` floats in [0.0, 1.0].
    """
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255.0, g / 255.0, b / 255.0


# ---------------------------------------------------------------------------
# BBox helpers
# ---------------------------------------------------------------------------


def bbox_is_degenerate(bbox: tuple[float, float, float, float], min_area: float = 0.01) -> bool:
    """Return True if the bbox has effectively zero area.

    Args:
        bbox: ``(x0, y0, x1, y1)`` tuple.
        min_area: Minimum area threshold in pt².

    Returns:
        True if area < min_area.
    """
    x0, y0, x1, y1 = bbox
    return (x1 - x0) * (y1 - y0) < min_area


def expand_bbox(
    bbox: tuple[float, float, float, float],
    margin: float = 0.5,
) -> fitz.Rect:
    """Expand a bbox by ``margin`` points on all sides.

    A small expansion is needed before redaction to catch sub-pixel glyph
    bleed — without it, hairline ink artifacts are left behind after
    ``apply_redactions()``.

    Args:
        bbox: ``(x0, y0, x1, y1)`` tuple.
        margin: Expansion in points (default 0.5).

    Returns:
        Expanded :class:`fitz.Rect`.
    """
    x0, y0, x1, y1 = bbox
    return fitz.Rect(x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def clamp_rect_to_page(rect: fitz.Rect, page: fitz.Page) -> fitz.Rect:
    """Clamp a rect so it does not exceed the page mediabox boundaries.

    Prevents redaction annotations from being rejected when a span bbox is
    reported slightly outside the page — a known quirk with some scanned PDFs.

    Args:
        rect: The rect to clamp.
        page: The page whose mediabox defines the bounds.

    Returns:
        Clamped :class:`fitz.Rect`.
    """
    mb = page.mediabox
    return fitz.Rect(
        max(rect.x0, mb.x0),
        max(rect.y0, mb.y0),
        min(rect.x1, mb.x1),
        min(rect.y1, mb.y1),
    )


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

AI_OUTPUT_WARNING = (
    "Output format 'ai' saves a PDF with a .ai extension — it is NOT a true native "
    "Adobe Illustrator file. To get a fully compatible .ai file, open the output in "
    "Adobe Illustrator and use File > Save As > Adobe Illustrator (.ai)."
)

AI_COMPAT_WARNING = (
    "Input is an Adobe Illustrator (.ai) file. LabelForge reads its embedded PDF "
    "compatibility layer. Edits may not fully preserve Illustrator-specific features "
    "when the file is reopened in Adobe Illustrator. For best results, export your "
    ".ai to PDF first (File > Save As > PDF, uncheck 'Preserve Illustrator Editing "
    "Capabilities') before editing."
)


def detect_file_type(path: Path) -> Literal["pdf", "ai"]:
    """Detect whether a file is a PDF or Adobe Illustrator file by extension.

    Args:
        path: Path to the input file.

    Returns:
        ``"ai"`` if the suffix is ``.ai``, otherwise ``"pdf"``.

    Raises:
        ValueError: If the extension is not ``.pdf`` or ``.ai``.
    """
    suffix = path.suffix.lower()
    if suffix == ".ai":
        return "ai"
    if suffix == ".pdf":
        return "pdf"
    raise ValueError(f"Unsupported file type {suffix!r}. Expected .pdf or .ai.")
