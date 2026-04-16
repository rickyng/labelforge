"""OCR handler for detecting text in outlined vector shapes.

Uses EasyOCR (optional) to recognise CJK and other text that has been
converted to vector outlines in AI/PDF files.  Gracefully degrades if
EasyOCR or its PyTorch dependency is not installed.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Lazy singleton — initialised on first use
_reader = None
_reader_langs: tuple[str, ...] = ()


def is_easyocr_available() -> bool:
    """Return True if the easyocr package can be imported."""
    try:
        import easyocr  # noqa: F401
        return True
    except ImportError:
        return False


def get_ocr_reader(
    languages: list[str] | None = None,
) -> "easyocr.Reader | None":  # type: ignore[name-defined]
    """Return a cached EasyOCR Reader for the requested languages.

    The Reader is expensive to initialise (downloads models on first run).
    Subsequent calls with the same language list return the cached instance.

    NOTE: EasyOCR's ``ch_sim`` model is only compatible with English (``en``).
    Korean (``ko``) and Japanese (``ja``) each require their own reader.
    The default ``["ch_sim", "en"]`` covers Chinese + English. For Korean or
    Japanese text, callers should pass the appropriate language list.

    Args:
        languages: ISO 639 codes recognised by EasyOCR.
            Defaults to ``["ch_sim", "en"]`` (Simplified Chinese + English).

    Returns:
        An ``easyocr.Reader`` instance, or *None* if EasyOCR is not installed.
    """
    global _reader, _reader_langs

    if languages is None:
        languages = ["ch_sim", "en"]

    lang_key = tuple(sorted(languages))

    if _reader is not None and _reader_langs == lang_key:
        return _reader

    try:
        import easyocr
        _reader = easyocr.Reader(lang_key, gpu=False, verbose=False)
        _reader_langs = lang_key
        logger.info("EasyOCR reader initialised for languages: %s", lang_key)
        return _reader
    except ImportError:
        logger.warning(
            "easyocr is not installed — OCR text detection skipped. "
            "Install with: pip install easyocr"
        )
        return None
    except Exception as exc:
        logger.error("Failed to initialise EasyOCR: %s", exc)
        return None


def ocr_shape_region(
    page: "fitz.Page",  # type: ignore[name-defined]
    bbox: tuple[float, float, float, float],
    dpi: int = 150,
    languages: list[str] | None = None,
) -> tuple[str | None, float, str | None]:
    """Render a region of a PDF page and run OCR on it.

    Args:
        page: PyMuPDF Page object.
        bbox: ``(x0, y0, x1, y1)`` in PDF point space.
        dpi: Resolution for the rasterised region (higher = more accurate OCR).
        languages: EasyOCR language codes.

    Returns:
        ``(text, confidence, language)`` — *text* is *None* when no text is
        detected or EasyOCR is unavailable.
    """
    reader = get_ocr_reader(languages)
    if reader is None:
        return None, 0.0, None

    import fitz

    # Clip to page bounds
    rect = fitz.Rect(bbox) & page.rect
    if rect.is_empty:
        return None, 0.0, None

    # Rasterise the region
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    clip = fitz.Rect(bbox)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)

    # Convert to numpy array (EasyOCR expects this or PIL Image)
    import numpy as np
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )

    # Run OCR
    results = reader.readtext(img)

    if not results:
        return None, 0.0, None

    # Combine all detected fragments
    texts: list[str] = []
    confidences: list[float] = []
    for detection in results:
        # EasyOCR returns: (bbox_polygon, text, confidence)
        _, text, conf = detection
        if text and conf > 0.3:
            texts.append(text)
            confidences.append(conf)

    if not texts:
        return None, 0.0, None

    combined_text = " ".join(texts)
    avg_confidence = sum(confidences) / len(confidences)

    logger.info(
        "OCR result for %s: '%s' (confidence %.2f)",
        bbox, combined_text, avg_confidence,
    )

    return combined_text, avg_confidence, None


def estimate_fontsize_from_bbox(
    bbox: tuple[float, float, float, float],
) -> float:
    """Estimate a font size (pt) from a bounding box height.

    A rough heuristic: fontsize ≈ bbox_height × 0.75.
    """
    height = bbox[3] - bbox[1]
    return max(round(height * 0.75, 1), 6.0)
