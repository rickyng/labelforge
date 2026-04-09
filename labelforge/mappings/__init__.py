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


def detect_mapping(component_ids: set[str]) -> str | None:
    """Return the first mapping name whose fingerprint is a subset of component_ids."""
    for name, fingerprint in MAPPING_FINGERPRINTS.items():
        if fingerprint <= component_ids:
            return name
    return None
