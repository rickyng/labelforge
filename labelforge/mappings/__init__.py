"""Auto-discovered mapping registry.

Every ``*.py`` file in this package that exports ``MAPPING_NAME``,
``FIELD_MAP``, ``FINGERPRINT``, and ``assign`` is automatically
registered.  Files may also export ``TEMPLATE_NAME`` and ``build_changes``
for the JSON-order pipeline.

Adding a new mapping means adding a single file — no other code changes
required.
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Callable

MAPPINGS: dict[str, dict[str, str]] = {}
MAPPING_FINGERPRINTS: dict[str, set[str]] = {}
_ASSIGN_FNS: dict[str, Callable] = {}
_TEMPLATE_MAPPINGS: dict[str, Callable] = {}
AI_FILE_MAP: dict[str, str] = {}
BARCODE_REGION_MAP: dict[str, dict[str, dict]] = {}
_GROUPING_MODES: dict[str, str] = {}  # template_name -> "span" | "line" | "block"
OCR_ZONES: dict[str, dict[str, tuple[float, float, float, float]]] = {}  # mapping_name -> {zone_name: bbox}
CJK_FALLBACK_FONTS: dict[str, str] = {}  # template_name -> font name


def _register(mod: ModuleType) -> None:
    # Pipeline 1 (CSV)
    name: str | None = getattr(mod, "MAPPING_NAME", None)
    fmap: dict[str, str] | None = getattr(mod, "FIELD_MAP", None)
    fp: set[str] | None = getattr(mod, "FINGERPRINT", None)
    fn: Callable | None = getattr(mod, "assign", None)
    if name and fmap and fp and fn:
        MAPPINGS[name] = fmap
        MAPPING_FINGERPRINTS[name] = fp
        _ASSIGN_FNS[name] = fn

    # Pipeline 2 (JSON order)
    template_name: str | None = getattr(mod, "TEMPLATE_NAME", None)
    build_fn: Callable | None = getattr(mod, "build_changes", None)
    if template_name and build_fn:
        _TEMPLATE_MAPPINGS[template_name] = build_fn

    # AI file binding
    ai_file: str | None = getattr(mod, "AI_FILE", None)
    if template_name and ai_file:
        AI_FILE_MAP[template_name] = ai_file

    # Barcode regions for vector-drawn barcodes not detected by pyzbar
    barcode_regions: dict | None = getattr(mod, "BARCODE_REGIONS", None)
    if name and barcode_regions:
        BARCODE_REGION_MAP[name] = barcode_regions

    # Grouping mode for component display
    grouping_mode: str | None = getattr(mod, "GROUPING_MODE", None)
    key = template_name or name
    if key and grouping_mode:
        _GROUPING_MODES[key] = grouping_mode

    # OCR zones for outlined text detection (CJK etc.)
    ocr_zones: dict | None = getattr(mod, "OCR_ZONES", None)
    if name and ocr_zones:
        OCR_ZONES[name] = ocr_zones

    # CJK fallback font for text insertion during apply
    cjk_font: str | None = getattr(mod, "CJK_FALLBACK_FONT", None)
    if key and cjk_font:
        CJK_FALLBACK_FONTS[key] = cjk_font


for _mi in pkgutil.iter_modules(__path__):
    _mod = importlib.import_module(f".{_mi.name}", package="labelforge.mappings")
    _register(_mod)


def get_assign_fn(mapping_name: str | None) -> Callable | None:
    """Return the per-mapping assign callable, or None."""
    return _ASSIGN_FNS.get(mapping_name or "")


def get_build_changes(template_name: str) -> Callable | None:
    """Return the build_changes callable for a template, or None."""
    return _TEMPLATE_MAPPINGS.get(template_name)


def get_ai_file(template_name: str) -> str | None:
    """Return the AI file path for a template, or None."""
    return AI_FILE_MAP.get(template_name)


def get_grouping_mode(template_name: str) -> str:
    """Return the grouping mode for a template.

    Returns "span", "line", or "block". Defaults to "span" if not defined.
    """
    return _GROUPING_MODES.get(template_name, "span")


def get_ocr_zones(mapping_name: str) -> dict[str, tuple[float, float, float, float]] | None:
    """Return OCR zones for a mapping, or None if not defined."""
    return OCR_ZONES.get(mapping_name)


def get_cjk_fallback_font(template_name: str) -> str | None:
    """Return the CJK fallback font for a template, or None if not defined."""
    return CJK_FALLBACK_FONTS.get(template_name)


def detect_mapping(component_ids: set[str]) -> str | None:
    """Return the first mapping name whose fingerprint is a subset of component_ids."""
    for name, fingerprint in MAPPING_FINGERPRINTS.items():
        if fingerprint <= component_ids:
            return name
    return None
