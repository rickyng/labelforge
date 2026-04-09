"""Mapping definition for the Mango GI label template."""
from __future__ import annotations

MAPPING_NAME: str = "mango_gi"
TEMPLATE_NAME: str = "GI001BAW-GI001BAC"
AI_FILE: str = "labelforge/templates/GI001BAW-GI001BAC_ai.ai"

FIELD_MAP: dict[str, str] = {
    "LINE_AGE_GENDER": "p0_t_b0_l0_s0",
    "SIZE":            "p0_t_b1_l0_s0",
    "COLOR_CODE":      "p0_t_b1_l1_s0",
    "REF_FIRST4":      "p0_t_b1_l2_s0",
    "REF_LAST4":       "p0_t_b1_l2_s1",
    "DESCRIPTION":     "p0_t_b2_l0_s0",
    "FAM_CODE":        "p0_t_b4_l0_s0",
}

FINGERPRINT: set[str] = {
    "p0_t_b0_l0_s0",
    "p0_t_b1_l2_s0",
    "p0_t_b2_l0_s0",
}


# ---------------------------------------------------------------------------
# Pipeline 2: JSON order → component mapping
# ---------------------------------------------------------------------------


def _val(by_id: dict, field_id: str, size_idx: int = 0) -> str:
    """Get raw value for a template field at a given size index."""
    f = by_id.get(field_id)
    if not f or not f["values"]:
        return ""
    vs = f["values"]
    if f["field_type"] == "per_size":
        return vs[size_idx] if size_idx < len(vs) and vs[size_idx] is not None else ""
    return vs[0] if vs[0] is not None else ""


def _color_val(by_id: dict, size_idx: int = 0) -> str:
    """Get color value: take first part before ':' from field '6'."""
    raw = _val(by_id, "6", size_idx)
    if not raw:
        return ""
    # "01:WHITE" → "01"
    parts = raw.split(":")
    return parts[0].strip() if parts else raw


def build_changes(resolved_fields: list[dict]) -> list[dict[str, str]]:
    """Map resolved template fields to component_id -> intended_value, one dict per size.

    Custom logic for GI:
    - REF first 4 gets "REF: " prefix
    - Colour gets "C: " prefix
    - Line + Age + Gender combined into LINE_AGE_GENDER component
    """
    by_id = {f["id"]: f for f in resolved_fields}

    # Determine size count
    size_count = 1
    for f in resolved_fields:
        if f["field_type"] == "per_size" and len(f["values"]) > size_count:
            size_count = len(f["values"])

    results = []
    for i in range(size_count):
        row: dict[str, str] = {}
        row["p0_t_b1_l2_s0"] = f"REF: {_val(by_id, '5.1', i)}"      # REF: first 4
        row["p0_t_b1_l2_s1"] = _val(by_id, "5.2", i)                  # REF last 4
        row["p0_t_b1_l1_s0"] = f"C:{_color_val(by_id, i)}"             # C: colour (code only)
        row["p0_t_b1_l0_s0"] = _val(by_id, "7", i)                    # SIZE

        row["p0_t_b0_l0_s0"] = _val(by_id, "4.1", i)

        row["p0_t_b2_l0_s0"] = _val(by_id, "8", i)                    # DESCRIPTION
        row["p0_t_b4_l0_s0"] = _val(by_id, "3", i)                    # FAM_CODE

        # Shape fill color: yellow → blue
        row["p0_shape_0"] = "#0057B8"

        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Pipeline 1: CSV import (existing)
# ---------------------------------------------------------------------------


def assign(row_values: dict[str, str], assign_fn) -> None:
    """Assign for GI template: line/age/gender, size, color, REF, description, fam code."""
    assign_fn("LINE_AGE_GENDER", row_values.get("LINE_AGE_GENDER", ""))
    assign_fn("SIZE", row_values.get("SIZE", ""))
    # Color: take first part before ':' if present
    raw_color = row_values.get("COLOR_CODE", "")
    color_code = raw_color.split(":")[0].strip() if ":" in raw_color else raw_color
    assign_fn("COLOR_CODE", f"C: {color_code}")
    assign_fn("REF_FIRST4", f"REF: {row_values.get('REF_FIRST4', '')}")
    assign_fn("REF_LAST4", row_values.get("REF_LAST4", ""))
    assign_fn("DESCRIPTION", row_values.get("DESCRIPTION", ""))
    assign_fn("FAM_CODE", row_values.get("FAM_CODE", ""))
