"""Reusable changes-generation logic extracted from generate_changes.py."""
from __future__ import annotations
import re
from typing import Any
from labelforge.component_models import DocumentComponent, ComponentType

_FIELD_PATTERNS: list[tuple[str, str]] = [
    (r"^\d{13}$", "EAN13"),
    (r"^(XXS|XS|S|M|L|XL|XXL|XXXL|1XL|2XL|3XL|4XL|\d{2,3})$", "SIZE"),
    (r"^\d{1,5}$", "UNITS"),
    (r"(?i)^ref[: ]", "REF"),
    (r"^\d{2} [A-Z]+$", "COLOR"),           # e.g. "01 WHITE"
    (r"(?i)^c[: ]\d+", "COLOR_CODE"),
    (r"(?i)^made in ", "ORIGIN"),
    (r"^\d{10}$", "PO_ID"),
    (r"^[A-Z0-9]{6,12}$", "STYLE_ID"),
    (r"(?i)^(SS|AW)\d{4}$", "SEASON"),
    (r"(?i)^iconic$", "ICONIC"),
    (r"^(WOMAN|MAN|KIDS|BOY|GIRL|UNISEX)$", "LINE"),
    (r"^(ADULT|JUNIOR|BABY)$", "AGE"),
    (r"^(FEMALE|MALE)$", "GENDER"),
]


def classify(text: str) -> str | None:
    """Return the semantic role of a text value, or None if unrecognised."""
    t = text.strip()
    for pattern, role in _FIELD_PATTERNS:
        if re.match(pattern, t):
            return role
    return None


def build_component_index(
    components: list[DocumentComponent],
) -> dict[str, list[DocumentComponent]]:
    """Group components by semantic role."""
    index: dict[str, list[DocumentComponent]] = {}
    for comp in components:
        if comp.type == ComponentType.BARCODE and comp.barcode_value:
            role = "EAN13"
        elif comp.type == ComponentType.TEXT and comp.text:
            role = classify(comp.text)
        else:
            role = None
        if role:
            index.setdefault(role, []).append(comp)
    return index


# Maps field names to their label IDs (used by both extract_fields and build_changes).
# LINE/AGE/GENDER all point to the combined slot; LABEL_ID_MAP uses LINE_AGE_GENDER.
LABEL_ID_MAP: dict[str, str] = {
    "SUPPLIER":        "p0_b14_l0_s0",
    "PO_ID":           "p0_b14_l1_s0",
    "REF_FIRST4":      "p0_b11_l0_s0",  # written as 'REF: ' + first 4 chars
    "REF_LAST4":       "p0_b11_l0_s1",
    "COLOR":           "p0_b11_l1_s0",
    "EAN13":           "p0_b9_l0_s0",
    "FAM_CODE":        "p0_b10_l0_s0",
    "LINE":            "p0_b10_l0_s1",
    "AGE":             "p0_b10_l0_s1",
    "GENDER":          "p0_b10_l0_s1",
    "LINE_AGE_GENDER": "p0_b10_l0_s1",  # combined field used by build_changes
    "SIZE":            "p0_b6_l0_s0",
    "SIZE_PACK":       "p0_b6_l1_s0",
    "ORIGIN":          "p0_b11_l2_s0",
    "PRODUCT_TYPE":    "p0_b8_l0_s0",
    "ICONIC":          "p0_b13_l0_s0",
}


# Ordered field spec for display
FIELD_SPEC: list[tuple[str, str, str]] = [
    ("1",   "UNITS",        "ItemData[#].SizePack.TotalSizePackQty"),
    ("2",   "SUPPLIER",     "Supplier.SupplierCode"),
    ("3",   "PO_ID",        "LabelOrder.Id"),
    ("4.1", "REF_FIRST4",   "StyleColor[0].ReferenceID[:4]"),
    ("4.2", "REF_LAST4",    "StyleColor[0].ReferenceID[4:]"),
    ("5",   "COLOR",        "MangoColorCode + Color"),
    ("6",   "EAN13",        "SizePack.SizeBarCode"),
    ("7",   "FAM_CODE",     "ProductTypeCodeLegacy"),
    ("8",   "LINE",         "Line"),
    ("8.1", "AGE",          "Age"),
    ("8.2", "GENDER",       "Gender"),
    ("9",   "SIZE",         "SizeNameES"),
    ("10",  "SIZE_PACK",    "SizePack.SizePackQty"),
    ("11",  "ORIGIN",       "Origin.countryorigin"),
    ("12",  "PRODUCT_TYPE", "ProductType"),
    ("13",  "ICONIC",       "Iconic"),
]


def extract_fields(
    style: dict[str, Any],
    item: dict[str, Any],
    order: dict[str, Any],
) -> list[dict[str, str]]:
    """Return the 13 named field values for one size as a list of {num, field, path, value}."""
    size_pack = item.get("SizePack", {})
    if not isinstance(size_pack, dict):
        size_pack = {}

    label_order = order.get("LabelOrder", {})
    if not isinstance(label_order, dict):
        label_order = {}

    ref_id = str(style.get("ReferenceID", ""))
    mango_color = item.get("MangoColorCode") or style.get("MangoColorCode", "")
    color_name = item.get("COLOR") or style.get("Color", "")
    color_val = f"{mango_color} {color_name}".strip() if mango_color else color_name
    origin_obj = style.get("Origin")
    origin = origin_obj.get("countryorigin", "") if isinstance(origin_obj, dict) else style.get("CountryOfOrigin", "")
    supplier = order.get("Supplier", {}).get("SupplierCode", "") if isinstance(order.get("Supplier"), dict) else ""

    raw: dict[str, str] = {
        "UNITS":        str(size_pack.get("TotalSizePackQty") or item.get("itemQty", "")),
        "SUPPLIER":     str(supplier),
        "PO_ID":        str((label_order.get("Id") or order.get("Id", ""))),
        "REF_FIRST4":   ref_id[:4] if len(ref_id) >= 4 else ref_id,
        "REF_LAST4":    ref_id[4:] if len(ref_id) >= 4 else "",
        "COLOR":        color_val,
        "EAN13":        str(size_pack.get("SizeBarCode") or item.get("EAN13") or item.get("EAN") or item.get("BarCode", "")),
        "FAM_CODE":     str(style.get("ProductTypeCodeLegacy") or style.get("FAMILYID", "")),
        "LINE":         str(style.get("Line", "")),
        "AGE":          str(style.get("Age", "")),
        "GENDER":       str(style.get("Gender", "")),
        "SIZE":         str(item.get("SizeNameES") or item.get("SizeName", "")),
        "SIZE_PACK":    str(size_pack.get("SizePackQty", "")),
        "ORIGIN":       f"MADE IN {origin.upper()}" if origin else "",
        "PRODUCT_TYPE": str(style.get("ProductType", "")),
        "ICONIC":       "ICONIC" if str(style.get("Iconic", "NO")).upper() == "YES" else "",
    }

    return [
        {
            "num": num,
            "field": field,
            "path": path,
            "value": raw.get(field, ""),
            "label_id": LABEL_ID_MAP.get(field, ""),
        }
        for num, field, path in FIELD_SPEC
    ]




def build_changes(
    style: dict[str, Any],
    item: dict[str, Any],
    order: dict[str, Any],
    index: dict[str, list[DocumentComponent]],
) -> dict[str, str]:
    """Return {label_id: new_value} for one size using the hardcoded LABEL_ID_MAP.

    JSON path mapping (Mango label format):
      SUPPLIER        <- Supplier.SupplierCode
      PO_ID           <- LabelOrder.Id
      REF_FIRST4      <- 'REF: ' + ReferenceID[:4]   -> p0_b11_l0_s0
      REF_LAST4       <- ReferenceID[4:]              -> p0_b11_l0_s1
      COLOR           <- MangoColorCode + ' ' + Color -> p0_b11_l1_s0
      EAN13           <- ItemData[#].SizePack.SizeBarCode
      FAM_CODE        <- ProductTypeCodeLegacy
      LINE_AGE_GENDER <- Line + ' ' + Age + ' ' + Gender
      SIZE            <- ItemData[#].SizeNameES
      SIZE_PACK       <- ItemData[#].SizePack.SizePackQty
      ORIGIN          <- Origin.countryorigin
      PRODUCT_TYPE    <- ProductType
      ICONIC          <- Iconic flag
    """
    changes: dict[str, str] = {}

    def _set(field: str, value: str) -> None:
        label_id = LABEL_ID_MAP.get(field)
        if label_id is not None:
            changes[label_id] = value

    size_pack = item.get("SizePack", {})
    if not isinstance(size_pack, dict):
        size_pack = {}

    # SUPPLIER
    supplier = order.get("Supplier", {}).get("SupplierCode", "") if isinstance(order.get("Supplier"), dict) else ""
    _set("SUPPLIER", str(supplier))

    # PO_ID — LabelOrder.Id or order top-level Id
    label_order = order.get("LabelOrder", {})
    po = (label_order.get("Id") if isinstance(label_order, dict) else None) or order.get("Id", "")
    _set("PO_ID", str(po))

    # REF_FIRST4 / REF_LAST4
    ref_id = str(style.get("ReferenceID", ""))
    _set("REF_FIRST4", f"REF: {ref_id[:4]}" if ref_id else "")
    _set("REF_LAST4", ref_id[4:] if len(ref_id) > 4 else "")

    # COLOR — "MangoColorCode Color" e.g. "01 WHITE"
    mango_color = item.get("MangoColorCode") or style.get("MangoColorCode", "")
    color_name = item.get("COLOR") or style.get("Color", "")
    color_val = f"{mango_color} {color_name}".strip() if mango_color else color_name
    _set("COLOR", color_val)

    # EAN13 — SizePack.SizeBarCode
    ean = size_pack.get("SizeBarCode") or item.get("EAN13") or item.get("EAN") or item.get("BarCode", "")
    _set("EAN13", str(ean) if ean else "")

    # FAM_CODE — ProductTypeCodeLegacy
    fam_code = style.get("ProductTypeCodeLegacy") or style.get("FAMILYID", "")
    _set("FAM_CODE", str(fam_code) if fam_code else "")

    # LINE_AGE_GENDER — combined into single label
    line = str(style.get("Line", ""))
    age = str(style.get("Age", ""))
    gender = str(style.get("Gender", ""))
    line_age_gender = " ".join(part for part in [line, age, gender] if part)
    _set("LINE_AGE_GENDER", line_age_gender)

    # SIZE — SizeNameES for EU size label
    size = item.get("SizeNameES") or item.get("SizeName", "")
    _set("SIZE", str(size) if size else "")

    # SIZE_PACK — SizePackQty
    size_pack_qty = size_pack.get("SizePackQty", "")
    _set("SIZE_PACK", str(size_pack_qty) if size_pack_qty else "")

    # ORIGIN — Origin.countryorigin
    origin_obj = style.get("Origin")
    if isinstance(origin_obj, dict):
        origin = origin_obj.get("countryorigin", "")
    else:
        origin = style.get("CountryOfOrigin", "")
    _set("ORIGIN", f"MADE IN {origin.upper()}" if origin else "")

    # PRODUCT_TYPE
    product_type = str(style.get("ProductType", ""))
    _set("PRODUCT_TYPE", product_type)

    # ICONIC
    is_iconic = str(style.get("Iconic", "NO")).upper() == "YES"
    _set("ICONIC", "ICONIC" if is_iconic else "")

    return changes