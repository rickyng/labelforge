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

# CJK font paths (Noto Sans CJK, Apple system fonts, common Linux fonts)
_CJK_FONT_PATHS: list[tuple[str, list[str]]] = [
    ("notosanscjksc", [
        "/System/Library/Fonts/Supplemental/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]),
    ("notosanscjkjp", [
        "/System/Library/Fonts/Supplemental/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]),
    ("notosanscjkkr", [
        "/System/Library/Fonts/Supplemental/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]),
    ("applesdgothicneokorean", [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]),
    ("hiragino", [
        "/System/Library/Fonts/Hiragino Sans W3.ttc",
        "/System/Library/Fonts/Hiragino Sans W6.ttc",
    ]),
    ("pingfangsc", [
        "/System/Library/Fonts/PingFang.ttc",
    ]),
]

# Unicode-capable fonts supporting CJK + Arabic + Cyrillic + more
_UNICODE_FONT_PATHS: list[str] = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/arial-unicode/Arial_Unicode.ttf",
    "/usr/share/fonts/truetype/arialuni.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/arialuni.ttf",
]


def contains_non_latin(text: str) -> bool:
    """Check if text contains non-Latin characters (CJK, Arabic, Cyrillic, etc.).

    Returns True if the text contains characters outside the basic Latin range
    that require a Unicode-capable font for proper rendering.

    Args:
        text: String to check for non-Latin characters.

    Returns:
        True if text contains CJK, Arabic, Cyrillic, Hangul, or Japanese characters.
    """
    if not text:
        return False

    for char in text:
        # CJK Unified Ideographs (common Chinese characters)
        if "\u4e00" <= char <= "\u9fff":
            return True
        # CJK Extension A (less common Chinese)
        if "\u3400" <= char <= "\u4dbf":
            return True
        # Arabic script
        if "\u0600" <= char <= "\u06ff":
            return True
        # Arabic Presentation Forms A/B (ligatures, etc.)
        if "\ufb50" <= char <= "\ufdff" or "\ufe70" <= char <= "\ufeff":
            return True
        # Cyrillic (Russian, Ukrainian, etc.)
        if "\u0400" <= char <= "\u04ff":
            return True
        # Cyrillic Supplement
        if "\u0500" <= char <= "\u052f":
            return True
        # Hangul (Korean syllables)
        if "\uac00" <= char <= "\ud7af":
            return True
        # Hiragana (Japanese)
        if "\u3040" <= char <= "\u309f":
            return True
        # Katakana (Japanese)
        if "\u30a0" <= char <= "\u30ff":
            return True
        # Hebrew
        if "\u0590" <= char <= "\u05ff":
            return True
        # Thai
        if "\u0e00" <= char <= "\u0e7f":
            return True
    return False


def resolve_unicode_font() -> str | None:
    """Find a Unicode-capable font supporting CJK, Arabic, Cyrillic, and more.

    Resolution order:
    1. Arial Unicode MS (most comprehensive, 23MB on macOS)
    2. System CJK fonts via resolve_cjk_font()

    Returns:
        Absolute path to a Unicode font file, or None if none found.
    """
    for p in _UNICODE_FONT_PATHS:
        if Path(p).exists():
            return p

    # Fall back to CJK font if no Unicode font found
    return resolve_cjk_font()


def resolve_cjk_font(language: str | None = None) -> str | None:
    """Find a CJK font file suitable for the given language.

    Resolution order:
    1. Language-specific Noto Sans CJK (sc, jp, kr)
    2. Generic Noto Sans CJK Regular
    3. Apple system fonts (macOS)

    Args:
        language: ISO 639-1 code (e.g., "zh", "ja", "ko") or None for any.

    Returns:
        Absolute path to a CJK font file, or None if none found.
    """
    # Language-specific preference
    lang_fragment = ""
    if language:
        lang_lower = language.lower()
        if lang_lower in ("zh", "ch_sim", "ch_tra"):
            lang_fragment = "sc"
        elif lang_lower in ("ja", "jp"):
            lang_fragment = "jp"
        elif lang_lower in ("ko", "kr"):
            lang_fragment = "kr"

    # Try language-specific first
    if lang_fragment:
        for fragment, paths in _CJK_FONT_PATHS:
            if lang_fragment in fragment:
                for p in paths:
                    if Path(p).exists():
                        return p

    # Fall back to any CJK font
    for fragment, paths in _CJK_FONT_PATHS:
        for p in paths:
            if Path(p).exists():
                return p

    return None


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


def extract_embedded_fonts(doc: fitz.Document) -> dict[str, bytes]:
    """Extract all embedded font streams from a PDF/AI document.

    Scans every page for font references, extracts their raw bytes via
    ``doc.extract_font(xref)``, and returns a mapping from the stripped
    lowercase font name to the font bytes.

    This allows the apply step to reuse fonts already embedded in the source
    document instead of falling back to system fonts or PyMuPDF built-ins.

    Args:
        doc: An open :class:`fitz.Document`.

    Returns:
        Dict mapping stripped-lowercase font name → raw font bytes.
        Only entries where actual bytes were returned are included.
    """
    seen_xrefs: set[int] = set()
    fonts: dict[str, bytes] = {}
    for page in doc:
        for font_entry in page.get_fonts(full=True):
            xref, _ext, _type, name, _enc = font_entry[0], font_entry[1], font_entry[2], font_entry[3], font_entry[4]
            if xref == 0 or xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                font_tuple = doc.extract_font(xref)
            except Exception:  # noqa: BLE001
                continue
            # fitz >= 1.23 returns a tuple (name, ext, type, content)
            content = font_tuple[3] if isinstance(font_tuple, (tuple, list)) and len(font_tuple) >= 4 else (font_tuple.get("content") if font_tuple else None)
            if not content:
                continue
            key = strip_subset_prefix(name).lower()
            if key and key not in fonts:
                fonts[key] = content
    logger.debug("Extracted %d embedded font(s) from document", len(fonts))
    return fonts


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
