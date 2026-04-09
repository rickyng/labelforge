"""Mapping definition for the Mango PV (price tag) label template."""
from __future__ import annotations

MAPPING_NAME: str = "mango_pv"
TEMPLATE_NAME: str = "PVPV0102-PVP002XG"
AI_FILE: str = "labelforge/templates/PVPV0102-PVP002XG_ai.ai"

FIELD_MAP: dict[str, str] = {
    "ORDER_ID":       "p0_t_b0_l0_s0",
    "LINE":           "p0_t_b0_l1_s0",
    "REF_NO":         "p0_t_b1_l0_s0",
    "EAN13":          "p0_t_b2_l0_s0",
    "SIZE_US":        "p0_t_b5_l0_s0",
    "SIZE_UK":        "p0_t_b7_l0_s0",
    "SIZE_MX":        "p0_t_b9_l0_s0",
    "SIZE_CN":        "p0_t_b11_l0_s0",
    "SIZE_IT":        "p0_t_b11_l1_s0",
    "SIZE_EUR":       "p0_t_b11_l2_s0",
    "SIZE_RANGE":     "p0_t_b12_l0_s1",
}

FINGERPRINT: set[str] = {
    "p0_t_b12_l0_s1",
    "p0_t_b13_l1_s0",
    "p0_t_b5_l0_s0",
}

BARCODE_REGIONS: dict[str, dict] = {
    "EAN13": {
        "bbox": (636.0, 365.0, 720.0, 395.0),
        "format": "ean13",
        "text_source": "p0_t_b2_l0_s0",
    },
}


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Pipeline 2: JSON order -> component mapping
# ---------------------------------------------------------------------------


def build_changes(resolved_fields: list[dict]) -> list[dict[str, str]]:
    """Map resolved template fields to component_id -> intended_value, one dict per size.

    Custom logic for PV:
    - REF_NO: "REF:" prefix + 4-digit spacing
    - EAN13: formatted for readability + triggers BARCODE_REGIONS
    - Size Range: "/" replaced by space
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
        row["p0_t_b0_l0_s0"] = _val(by_id, "3", i)                 # ORDER_ID
        row["p0_t_b0_l1_s0"] = _val(by_id, "5", i)                 # LINE
        # REF_NO: add "REF: " prefix and space-separate every 4 digits
        ref_raw = _val(by_id, "7", i)
        ref_formatted = " ".join([ref_raw[j:j+4] for j in range(0, len(ref_raw), 4)]) if ref_raw else ""
        row["p0_t_b1_l0_s0"] = f"REF: {ref_formatted}" if ref_formatted else ""

        # EAN13: format as space-separated for readability (e.g. "8 431729 573797")
        # Also triggers BARCODE_REGIONS to generate barcode image above
        ean_raw = _val(by_id, "12", i)
        if ean_raw and len(ean_raw) == 13:
            row["p0_t_b2_l0_s0"] = f"{ean_raw[0]} {ean_raw[1:7]} {ean_raw[7:]}"
        else:
            row["p0_t_b2_l0_s0"] = ean_raw

        # Family + Generic
        row["p0_t_b12_l0_s1"] = _val(by_id, "30", i).replace("/", " ")  # Size Range: XXS/XS/S → XXS XS S

        row["p0_t_b11_l2_s0"] = _val(by_id, "20", i) # EUR SIZE
        row["p0_t_b11_l1_s0"] = _val(by_id, "20", i) # IT SIZE
        row["p0_t_b7_l0_s0"] = _val(by_id, "21", i) # UK SIZE
        row["p0_t_b5_l0_s0"] = _val(by_id, "22", i) # US SIZE
        row["p0_t_b9_l0_s0"] = _val(by_id, "23", i) # MEX SIZE
        row["p0_t_b11_l0_s0"] = _val(by_id, "24", i) # CN SIZE
        
        # SAP code
        row["p0_t_b14_l0_s0"] = _val(by_id, "39", i)               # SAP CODE

        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Pipeline 1: CSV import (existing)
# ---------------------------------------------------------------------------


def assign(row_values: dict[str, str], assign_fn) -> None:
    """Assign for PV (price tag) template: multi-region sizes, EAN13, REF_NO, etc."""
    assign_fn("ORDER_ID", row_values.get("PO_ID", ""))
    assign_fn("LINE", row_values.get("LINE", ""))
    assign_fn("REF_NO", row_values.get("REF_NO", ""))
    assign_fn("EAN13", row_values.get("EAN13", ""))
    assign_fn("SIZE_US", row_values.get("SIZE_US", ""))
    assign_fn("SIZE_UK", row_values.get("SIZE_UK", ""))
    assign_fn("SIZE_MX", row_values.get("SIZE_MX", ""))
    assign_fn("SIZE_CN", row_values.get("SIZE_CN", ""))
    assign_fn("SIZE_IT", row_values.get("SIZE_IT", ""))
    assign_fn("SIZE_EUR", row_values.get("SIZE_EUR", ""))
    assign_fn("SIZE_RANGE", row_values.get("SIZE_RANGE", ""))
