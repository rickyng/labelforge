"""Mapping definition for the Mango GI000DPO-SAP composition/care label template."""
from __future__ import annotations

MAPPING_NAME: str = "mango_gi000dpo"
TEMPLATE_NAME: str = "GI000DPO-SAP_1"
AI_FILE: str = "labelforge/templates/GI000DPO-SAP_1_ai.ai"
GROUPING_MODE: str = "block"  # Group text spans by PDF block for display
PROXIMITY_THRESHOLD: float = 3.0  # Merge blocks within 3 PDF points (vertical gap)

# CJK fallback font used when inserting OCR-detected text during apply
CJK_FALLBACK_FONT: str = "Noto Sans CJK SC"

# OCR zones: bounding boxes for regions containing outlined CJK text.
# These are (x0, y0, x1, y1) in PDF point space — measure from the AI file.
# TODO: Fill in actual bbox coordinates for each zone.
OCR_ZONES: dict[str, tuple[float, float, float, float]] = {
    "zone_c_trim": (0.0, 0.0, 0.0, 0.0),       # Triman logo region
    "zone_e_french": (0.0, 0.0, 0.0, 0.0),     # French compliance text
    "zone_f_korean": (0.0, 0.0, 0.0, 0.0),     # Korean symbol
    "zone_g_russian": (0.0, 0.0, 0.0, 0.0),    # Russian text
}

FIELD_MAP: dict[str, str] = {
    # FRONT section - Article and SET A
    "ARTICLE_NO_FRONT": "p0_t_b0_l0_s0",
    "SET_A": "p0_t_b1_l0_s0",
    "COSER_AQUI_FRONT": "p0_t_b2_l0_s0",

    # Zone Z - Composition (block 3 = FRONT composition)
    # Block 3 contains "90% POLYAMIDE..." multi-language composition
    "COMP_1_PCT": "p0_t_b3_l7_s4",   # " 90" percentage number
    "COMP_1_NAME": "p0_t_b3_l0_s0",   # Full multi-language fabric name line

    # BACK section - Article and SET B
    "ARTICLE_NO_BACK": "p0_t_b9_l0_s0",
    "SET_B": "p0_t_b10_l0_s0",
    "COSER_AQUI_BACK": "p0_t_b11_l0_s0",

    # Zone Z - Composition BACK (block 4 = BACK composition)
    # Block 4 contains "10% PVC..." multi-language composition
    "COMP_2_PCT": "p0_t_b4_l8_s3",   # " 10" percentage number
    "COMP_2_NAME": "p0_t_b4_l0_s0",   # Full multi-language fabric name line

    # Zone Z - Composition BACK 2 (block 5 = additional composition)
    # Block 5 contains "100% PVC..." multi-language composition
    "COMP_3_PCT": "p0_t_b5_l7_s3",   # " 100" percentage number
    "COMP_3_NAME": "p0_t_b5_l0_s0",   # Full multi-language fabric name line

    # Zone A - Country of Origin (multi-language) - placeholder
    "COUNTRY_ORIGIN": "p0_t_zone_a_0",

    # Zone B - Importer Text - placeholder
    "IMPORTER_TEXT": "p0_t_zone_b_0",

    # Zone C - Triman Logo (flag/shape) - placeholder
    "TRIMAN_LOGO": "p0_zone_c_trim",

    # Zone D - EAC Symbol - placeholder
    "EAC_SYMBOL": "p0_zone_d_eac",

    # Zone E - French Compliance Text - placeholder
    "FRENCH_TEXT": "p0_zone_e_french",

    # Zone F - Korean Symbol - placeholder
    "KOREAN_SYMBOL": "p0_zone_f_korean",

    # Zone G - Russian Age Text - placeholder
    "RUSSIAN_TEXT": "p0_zone_g_russian",
}

FINGERPRINT: set[str] = {
    "p0_t_b7_l0_s0",   # "GI000SE1 Composition Data Label"
    "p0_t_b14_l0_s0",  # "GI000SE1 Care Instructions Data Label"
}


# ---------------------------------------------------------------------------
# Pipeline 2: JSON order → component mapping
# ---------------------------------------------------------------------------


def _val(by_id: dict, field_id: str, size_idx: int = 0) -> str:
    """Get raw value for a template field at a given size index."""
    f = by_id.get(field_id)
    if not f or not f.get("values"):
        return ""
    vs = f["values"]
    if f["field_type"] == "per_size":
        return vs[size_idx] if size_idx < len(vs) and vs[size_idx] is not None else ""
    return vs[0] if vs[0] is not None else ""


def _translated(by_id: dict, field_id: str, size_idx: int = 0) -> str:
    """Get translated value for a template field at a given size index.

    Prefers translated_values over raw values. For multi-language strings,
    returns the full concatenated string.
    """
    f = by_id.get(field_id)
    if not f:
        return ""

    # Prefer translated_values (contains multi-language strings)
    vs = f.get("translated_values") or f.get("values", [])
    if not vs:
        return ""

    if f.get("field_type") == "per_size":
        return vs[size_idx] if size_idx < len(vs) and vs[size_idx] is not None else ""
    return vs[0] if vs[0] is not None else ""


def build_changes(resolved_fields: list[dict]) -> list[dict[str, str]]:
    """Map resolved template fields to component_id -> intended_value, one dict per size.

    Uses translated values for:
    - Composition fabric names (Zone Z)
    - Country of origin (Zone A)
    - Importer text (Zone B)
    - Special zones (C, D, E, F, G) from JSON-RULES
    """
    by_id = {f["id"]: f for f in resolved_fields}

    # Determine size count
    size_count = 1
    for f in resolved_fields:
        if f["field_type"] == "per_size" and len(f.get("values", [])) > size_count:
            size_count = len(f["values"])

    results = []
    for i in range(size_count):
        row: dict[str, str] = {}

        # Article number (appears in both FRONT and BACK sections)
        # Using SC1 which is StyleColor[0].ReferenceID
        article = _val(by_id, "SC1", i)
        row["p0_t_b0_l0_s0"] = article   # FRONT article (block 0)
        row["p0_t_b9_l0_s0"] = article    # BACK article (block 9)

        # SET designations (fixed values per PDF spec)
        row["p0_t_b1_l0_s0"] = "SET A"    # SET_A (FRONT block 1)
        row["p0_t_b10_l0_s0"] = "SET B"   # SET_B (BACK block 10)

        # COSER AQUÍ / SEWN HERE (both sides)
        row["p0_t_b2_l0_s0"] = "COSER AQUÍ/SEWN HERE"   # FRONT (block 2)
        row["p0_t_b11_l0_s0"] = "COSER AQUÍ/SEWN HERE"  # BACK (block 11)

        # Composition percentages and fabric names (Zone Z)
        # FRONT composition (block 3): CM6 = %, CM3_TXT = multi-language name
        row["p0_t_b3_l7_s4"] = _val(by_id, "CM6", i)           # 1st fabric % (block 3, line 7, span 4)
        row["p0_t_b3_l0_s0"] = _translated(by_id, "CM3_TXT", i)  # 1st fabric name (multi-lang)

        # BACK composition (block 4): CM10 = %, CM7_TXT = multi-language name
        row["p0_t_b4_l8_s3"] = _val(by_id, "CM10", i)          # 2nd fabric % (block 4, line 8, span 3)
        row["p0_t_b4_l0_s0"] = _translated(by_id, "CM7_TXT", i)   # 2nd fabric name (multi-lang)

        # BACK composition 2 (block 5): CM14 = %, CM11_TXT = multi-language name
        row["p0_t_b5_l7_s3"] = _val(by_id, "CM14", i)          # 3rd fabric % (block 5, line 7, span 3)
        row["p0_t_b5_l0_s0"] = _translated(by_id, "CM11_TXT", i)  # 3rd fabric name (multi-lang)

        # Country of origin (Zone A) - multi-language
        row["p0_t_zone_a_0"] = _translated(by_id, "ZA1", i)

        # Importer text (Zone B)
        row["p0_t_zone_b_0"] = _translated(by_id, "ZB_IMP", i)

        # Rule-based zones (from JSON-RULES)
        row["p0_zone_c_trim"] = _translated(by_id, "ZC_TRIM", i)    # Triman flag
        row["p0_zone_d_eac"] = _translated(by_id, "ZD_EAC", i)      # EAC symbol
        row["p0_zone_e_french"] = _translated(by_id, "ZE_FRENCH", i) # French compliance
        row["p0_zone_f_korean"] = _translated(by_id, "ZF_KOREAN", i) # Korean symbol
        row["p0_zone_g_russian"] = _translated(by_id, "ZG_RUSSIAN", i) # Russian text

        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Pipeline 1: CSV import (existing)
# ---------------------------------------------------------------------------


def assign(row_values: dict[str, str], assign_fn) -> None:
    """Assign for GI000DPO-SAP template: article numbers, sets, composition percentages."""
    # Article number (same value for both FRONT and BACK)
    article_no = row_values.get("ARTICLE_NO", "")
    assign_fn("ARTICLE_NO_FRONT", article_no)
    assign_fn("ARTICLE_NO_BACK", article_no)

    # SET designations
    assign_fn("SET_A", row_values.get("SET_A", ""))
    assign_fn("SET_B", row_values.get("SET_B", ""))

    # Composition percentages
    assign_fn("COMP_1_PCT", row_values.get("COMP_1_PCT", ""))
    assign_fn("COMP_2_PCT", row_values.get("COMP_2_PCT", ""))
    assign_fn("COMP_3_PCT", row_values.get("COMP_3_PCT", ""))