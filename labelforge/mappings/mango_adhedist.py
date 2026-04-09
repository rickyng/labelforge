"""Mapping definition for the Mango ADHEDIST label template."""
from __future__ import annotations

MAPPING_NAME: str = "mango_adhedist"
TEMPLATE_NAME: str = "ADHEDIST-mango"
AI_FILE: str = "labelforge/templates/ADHEDIST-mango_edit_no1_v2.ai"

FIELD_MAP: dict[str, str] = {
    "SUPPLIER":        "p0_t_b14_l0_s0",
    "PO_ID":           "p0_t_b14_l1_s0",
    "REF_FIRST4":      "p0_t_b11_l0_s0",
    "REF_LAST4":       "p0_t_b11_l0_s1",
    "COLOR":           "p0_t_b11_l1_s0",
    "FAM_CODE":        "p0_t_b10_l0_s0",
    "EAN13":           "p0_t_b9_l0_s0",
    "LINE_AGE_GENDER": "p0_t_b10_l0_s1",
    "SIZE":            "p0_t_b6_l0_s0",
    "SIZE_PACK":       "p0_t_b6_l1_s0",
    "ORIGIN":          "p0_t_b11_l2_s0",
    "PRODUCT_TYPE":    "p0_t_b8_l0_s0",
    "ICONIC":          "p0_t_b13_l0_s0",
}

FINGERPRINT: set[str] = {
    "p0_t_b6_l1_s0",
    "p0_t_b8_l0_s0",
    "p0_t_b11_l2_s0",
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


def build_changes(resolved_fields: list[dict]) -> list[dict[str, str]]:
    """Map resolved template fields to component_id -> intended_value, one dict per size.

    Custom logic for ADHEDIST:
    - REF first 4 gets "REF: " prefix
    - Colour gets "C: " prefix
    - Age + Gender combined into LINE_AGE_GENDER component
    - ICONIC: only set when value is YES/ICONIC
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
        row["p0_t_b14_l0_s0"] = _val(by_id, "2", i)                     # SUPPLIER
        row["p0_t_b14_l1_s0"] = _val(by_id, "3", i)                     # PO_ID
        row["p0_t_b11_l0_s0"] = f"REF: {_val(by_id, '4.1', i)}"      # REF: first 4
        row["p0_t_b11_l0_s1"] = _val(by_id, "4.2", i)                     # REF last 4
        row["p0_t_b11_l1_s0"] = f"C: {_val(by_id, '5', i)}"            # C: colour
        row["p0_t_b10_l0_s0"] = _val(by_id, "7", i)                     # FAM_CODE
        row["p0_t_b9_l0_s0"] = _val(by_id, "6", i)                      # EAN13

        # Age + Gender -> LINE_AGE_GENDER
        age = _val(by_id, "8.1", i)
        gender = _val(by_id, "8.2", i)
        row["p0_t_b10_l0_s1"] = f"{age} {gender}".strip() if age or gender else ""

        row["p0_t_b6_l0_s0"] = _val(by_id, "9", i)                      # SIZE
        row["p0_t_b6_l1_s0"] = _val(by_id, "10", i)                     # SIZE_PACK
        row["p0_t_b11_l2_s0"] = f"MADE IN {_val(by_id, '11', i).upper()}"  # ORIGIN
        row["p0_t_b8_l0_s0"] = _val(by_id, "12", i)                     # PRODUCT_TYPE

        iconic = _val(by_id, "13", i)
        if iconic.upper() in ("YES", "ICONIC"):
            row["p0_t_b13_l0_s0"] = "ICONIC"

        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Pipeline 1: CSV import (existing)
# ---------------------------------------------------------------------------


def assign(row_values: dict[str, str], assign_fn) -> None:
    """Assign for ADHEDIST template: supplier, REF, EAN13, origin, iconic, etc."""
    assign_fn("SUPPLIER", row_values.get("SUPPLIER", ""))
    assign_fn("PO_ID", row_values.get("PO_ID", ""))
    assign_fn("REF_FIRST4", f"REF: {row_values.get('REF_FIRST4', '')}")
    assign_fn("REF_LAST4", row_values.get("REF_LAST4", ""))
    assign_fn("COLOR_CODE", f"C: {row_values.get('COLOR_CODE', '')}")
    assign_fn("FAM_CODE", row_values.get("FAM_CODE", ""))
    assign_fn("EAN13", row_values.get("EAN13", ""))
    assign_fn("LINE_AGE_GENDER", row_values.get("LINE_AGE_GENDER", ""))
    assign_fn("SIZE", row_values.get("SIZE", ""))
    assign_fn("SIZE_PACK", row_values.get("SIZE_PACK", ""))
    assign_fn("ORIGIN", row_values.get("ORIGIN", ""))
    assign_fn("PRODUCT_TYPE", row_values.get("PRODUCT_TYPE", ""))
    iconic = row_values.get("ICONIC", "")
    if iconic.upper() in ("YES", "ICONIC"):
        assign_fn("ICONIC", "ICONIC")
