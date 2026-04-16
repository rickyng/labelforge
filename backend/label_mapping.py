"""Label template mapping configuration.

Embeds the field definitions from json_matching.json as Python data.
Each template maps PDF label references to JSON path expressions.
"""

from __future__ import annotations

import re


def _classify_field(json_path: str) -> str:
    """Classify a field as single, per_size, or unmapped."""
    if not json_path:
        return "unmapped"
    if "[#]" in json_path:
        return "per_size"
    return "single"


# ---------------------------------------------------------------------------
# Path evaluation (ported from scripts/resolve_mapping.py)
# ---------------------------------------------------------------------------


def _resolve_path_part(obj: object, part: str):
    """Resolve a single part like 'StyleColor[0]' or 'Color'."""
    if not part:
        return obj
    m = re.match(r"^(.+?)\[(\d+)\]$", part)
    if m:
        key, idx = m.group(1), int(m.group(2))
        obj = obj[key]
        return obj[idx]
    return obj[part]


def _resolve_simple_path(data: dict, path: str):
    """Walk a dot-separated path (without [#] or expressions) against data."""
    parts = path.split(".")
    cur = data
    for part in parts:
        cur = _resolve_path_part(cur, part)
    return cur


def _expand_wildcard_path(data: dict, path: str) -> list:
    """Expand a path containing exactly one [#] into a list of values."""
    segments = path.split(".")
    before, after = [], []
    found = False
    base = ""
    for seg in segments:
        if not found and "[#]" in seg:
            base = seg.replace("[#]", "")
            found = True
            continue
        if not found:
            before.append(seg)
        else:
            after.append(seg)

    cur = data
    for seg in before:
        cur = _resolve_path_part(cur, seg)

    arr = cur[base] if base else cur
    if not isinstance(arr, list):
        arr = [arr]

    results = []
    for item in arr:
        inner = item
        for seg in after:
            inner = _resolve_path_part(inner, seg)
        results.append(inner)
    return results


def _resolve_transform(path: str, value) -> str | None:
    """Handle (first N) / (last N) transform suffixes."""
    m = re.match(r"^(.+?)\s+\(first\s+(\d+)\)$", path)
    if m:
        return str(value)[: int(m.group(2))]
    m = re.match(r"^(.+?)\s+\(last\s+(\d+)\)$", path)
    if m:
        return str(value)[-int(m.group(2)) :]
    return None


def _resolve_expression(data: dict, expr: str):
    """Evaluate a json path expression (concat, transforms, wildcards, simple paths)."""
    expr = expr.strip()
    if not expr:
        return None

    # Concatenation: A + "sep" + B
    if "+" in expr:
        parts = [p.strip() for p in expr.split("+")]
        resolved = []
        for part in parts:
            if part.startswith('"') and part.endswith('"'):
                resolved.append(part[1:-1])
            else:
                resolved.append(str(_resolve_expression(data, part) or ""))
        return "".join(resolved)

    # Transform: path (first N) / (last N)
    if re.search(r"\((?:first|last)\s+\d+\)$", expr):
        base_match = re.match(r"^(.+?)\s+\((?:first|last)\s+\d+\)$", expr)
        if base_match:
            base_path = base_match.group(1)
            val = _resolve_expression(data, base_path)
            result = _resolve_transform(expr, val)
            if result is not None:
                return result

    # [#] wildcard
    if "[#]" in expr:
        return _expand_wildcard_path(data, expr)

    # Simple dot path
    try:
        return _resolve_simple_path(data, expr)
    except (KeyError, IndexError, TypeError):
        return None


def _apply_translation(
    values: list[str | None], translate_spec: dict, order: dict
) -> tuple[list[str | None], list[str | None], dict[str, dict[str, str]]]:
    """Apply translation lookup to resolved values.

    Args:
        values: Raw resolved values (codes like "C005", "MA")
        translate_spec: Translation specification dict with keys:
            - sheet: Excel sheet name (required)
            - multi_lang: If True, return multi-language string
            - type: "simple", "importer", or "country"
        order: Full order JSON for context

    Returns:
        Tuple of (translated_values, fallback_values, translations_by_lang)
    """
    from labelforge.mappings.translation import (
        translate,
        get_multi_language_string,
        get_importer_text,
        get_rules_from_order,
        get_russian_age_text,
    )

    translated: list[str | None] = []
    fallback: list[str | None] = []
    by_lang: dict[str, dict[str, str]] = {}

    sheet = translate_spec.get("sheet")
    multi_lang = translate_spec.get("multi_lang", False)
    translate_type = translate_spec.get("type", "simple")

    for i, raw_val in enumerate(values):
        if raw_val is None or raw_val == "":
            translated.append(None)
            fallback.append(raw_val)
            continue

        result = None
        lang_dict: dict[str, str] = {}

        if translate_type == "importer":
            # Importer lookup by destination
            result = get_importer_text(raw_val)
        elif translate_type == "country":
            # Country of origin - multi-language
            if multi_lang:
                result = get_multi_language_string(raw_val, sheet)
            else:
                result = translate(raw_val, sheet, "SPANISH")
        elif translate_type == "rules":
            # JSON-RULES lookup
            rules = get_rules_from_order(order)
            field_name = translate_spec.get("field")
            result = rules.get(field_name)
            if result is not None:
                result = str(result) if not isinstance(result, str) else result
        elif translate_type == "russian_age":
            # Special Russian age text lookup
            size_group = raw_val
            line_path = translate_spec.get("line_path", "StyleColor[0].Line")
            line = _resolve_expression(order, line_path) if line_path else None
            result = get_russian_age_text(size_group, line)
        elif translate_type == "multi":
            # Multi-language string for any sheet
            result = get_multi_language_string(raw_val, sheet)
        else:
            # Simple translation
            if multi_lang:
                result = get_multi_language_string(raw_val, sheet)
            else:
                result = translate(raw_val, sheet, "SPANISH")

        translated.append(result)
        fallback.append(raw_val)
        if result:
            by_lang[str(i)] = {"default": result}

    return translated, fallback, by_lang


def resolve_template_fields(template_name: str, order_data: dict) -> dict | None:
    """Resolve all template field json_paths against order JSON data.

    Returns a dict with template_name, size_count, size_names, and fields
    (each with id, pdf_reference, json_path, field_type, and values).
    Returns None if the template is not found.
    """
    fields_def = LABEL_TEMPLATES.get(template_name)
    if fields_def is None:
        return None

    # Use first element if order_data is a list (top-level array)
    order = order_data[0] if isinstance(order_data, list) else order_data

    resolved_fields: list[dict] = []
    max_size_count = 0

    for f in fields_def:
        json_path = f["json_path"]
        translate_spec = f.get("translate")
        field_type = _classify_field(json_path)

        values: list[str | None] = []
        translated_values: list[str | None] = []
        translations_by_lang: dict[str, dict[str, str]] = {}

        if json_path:
            result = _resolve_expression(order, json_path)
            if isinstance(result, list):
                values = [str(v) if v is not None else None for v in result]
                if field_type == "per_size":
                    max_size_count = max(max_size_count, len(values))
            else:
                values = [str(result) if result is not None else None]

            # Apply translation if specified
            if translate_spec:
                translated_values, _, translations_by_lang = _apply_translation(
                    values, translate_spec, order
                )

        resolved_fields.append({
            "id": f["id"],
            "pdf_reference": f["pdf_reference"],
            "json_path": json_path,
            "field_type": field_type,
            "values": values,
            "translated_values": translated_values if translate_spec else values,
            "translations_by_lang": translations_by_lang if translate_spec else {},
        })

    # Derive size names: prefer a field with "SizeName" in its json_path
    size_names: list[str] = []
    for rf in resolved_fields:
        if rf["field_type"] == "per_size" and rf["values"] and "SizeName" in (rf["json_path"] or ""):
            size_names = rf["values"]
            break
    # Fallback: use first per_size field with values
    if not size_names:
        for rf in resolved_fields:
            if rf["field_type"] == "per_size" and rf["values"]:
                size_names = rf["values"]
                break

    return {
        "template_name": template_name,
        "size_count": max_size_count,
        "size_names": size_names,
        "fields": resolved_fields,
    }


def build_component_changes(template_name: str, order_data: dict) -> dict | None:
    """Resolve template fields and map them to component IDs via the mapping file.

    Returns a dict with:
    - template_name, size_count, size_names, fields (raw resolved values)
    - changes: list of {component_id: intended_value}, one per size

    Returns None if the template is not found or has no mapping file.
    """
    from labelforge.mappings import get_build_changes

    resolved = resolve_template_fields(template_name, order_data)
    if resolved is None:
        return None

    build_fn = get_build_changes(template_name)
    if build_fn is None:
        return resolved  # No mapping file — return raw fields only

    changes = build_fn(resolved["fields"])
    return {**resolved, "changes": changes}


# ---------------------------------------------------------------------------
# Template data (source: labelforge/mappings/json_matching.json)
# ---------------------------------------------------------------------------

LABEL_TEMPLATES: dict[str, list[dict]] = {
    "GI000DPO-SAP_1": [
        # === Article number (used in FRONT and BACK) ===
        {"id": "SC1", "pdf_reference": "Article No.", "json_path": "StyleColor[0].ReferenceID"},
        # === Composition percentages ===
        {"id": "CM6", "pdf_reference": "Composition 1 %", "json_path": "StyleColor[0].Composition[0].Fabric[0].FabricPercent"},
        {"id": "CM10", "pdf_reference": "Composition 2 %", "json_path": "StyleColor[0].Composition[0].Fabric[1].FabricPercent"},
        {"id": "CM14", "pdf_reference": "Composition 3 %", "json_path": "StyleColor[0].Composition[0].Fabric[2].FabricPercent"},
        # === Composition fabric names (translated, multi-language) ===
        {"id": "CM3_TXT", "pdf_reference": "Composition 1 Name",
         "json_path": "StyleColor[0].Composition[0].Fabric[0].Fabricode",
         "translate": {"sheet": "MATERIALS", "type": "multi"}},
        {"id": "CM7_TXT", "pdf_reference": "Composition 2 Name",
         "json_path": "StyleColor[0].Composition[0].Fabric[1].Fabricode",
         "translate": {"sheet": "MATERIALS", "type": "multi"}},
        {"id": "CM11_TXT", "pdf_reference": "Composition 3 Name",
         "json_path": "StyleColor[0].Composition[0].Fabric[2].Fabricode",
         "translate": {"sheet": "MATERIALS", "type": "multi"}},
        # === Zone A: Country of Origin (multi-language) ===
        {"id": "ZA1", "pdf_reference": "Zone A Country of Origin",
         "json_path": "StyleColor[0].Origin.Code_Country",
         "translate": {"sheet": "MADE IN COUNTRY", "type": "country", "multi_lang": True}},
        # === Zone B: Importer Text ===
        {"id": "ZB_IMP", "pdf_reference": "Zone B Importer Text",
         "json_path": "StyleColor[0].Destination.dc",
         "translate": {"type": "importer"}},
        # === Zone C: Triman Logo (from JSON-RULES) ===
        {"id": "ZC_TRIM", "pdf_reference": "Zone C Triman Logo",
         "json_path": "StyleColor[0].ProductTypeCodeLegacy",
         "translate": {"type": "rules", "field": "triman"}},
        # === Zone D: EAC Symbol (from JSON-RULES) ===
        {"id": "ZD_EAC", "pdf_reference": "Zone D EAC Symbol",
         "json_path": "StyleColor[0].ProductTypeCodeLegacy",
         "translate": {"type": "rules", "field": "eac"}},
        # === Zone E: French Compliance Text (from JSON-RULES) ===
        {"id": "ZE_FRENCH", "pdf_reference": "Zone E French Compliance",
         "json_path": "StyleColor[0].ProductTypeCodeLegacy",
         "translate": {"type": "rules", "field": "french_text"}},
        # === Zone F: Korean Symbol (from JSON-RULES) ===
        {"id": "ZF_KOREAN", "pdf_reference": "Zone F Korean Symbol",
         "json_path": "StyleColor[0].ProductTypeCodeLegacy",
         "translate": {"type": "rules", "field": "korean_symbol"}},
        # === Zone G: Russian Age Text ===
        {"id": "ZG_RUSSIAN", "pdf_reference": "Zone G Russian Age Text",
         "json_path": "StyleColor[0].SizeGroupLegay",
         "translate": {"type": "russian_age", "line_path": "StyleColor[0].Line"}},
    ],
    "PVPV0102-PVP002XG": [
        {"id": "1", "pdf_reference": "ITEM DATATQTY", "json_path": "StyleColor[0].ItemData[#].itemQty"},
        {"id": "2", "pdf_reference": "Code of supplier", "json_path": "Supplier.SupplierCode"},
        {"id": "3", "pdf_reference": "Code of order", "json_path": "LabelOrder.Id"},
        {"id": "4", "pdf_reference": "FAM CODE", "json_path": "StyleColor[0].ProductTypeCodeLegacy"},
        {"id": "5", "pdf_reference": "FAM LINE DESCRIPTION", "json_path": "StyleColor[0].Line"},
        {"id": "6", "pdf_reference": '"P" Graphic', "json_path": "StyleColor[0].Iconic"},
        {"id": "7", "pdf_reference": "Reference number", "json_path": "StyleColor[0].ReferenceID"},
        {"id": "8", "pdf_reference": "Reference number (suffix)", "json_path": "StyleColor[0].StyleID"},
        {"id": "9", "pdf_reference": "Colour of garment", "json_path": "StyleColor[0].Color"},
        {"id": "10", "pdf_reference": "BLOCK of the garment", "json_path": "StyleColor[0].ProductTypeCodeLegacy"},
        {"id": "11", "pdf_reference": "Distribution mark", "json_path": "StyleColor[0].Destination.de_code"},
        {"id": "12", "pdf_reference": "BAR CODE EAN13", "json_path": "StyleColor[0].ItemData[#].EAN13"},
        {"id": "13", "pdf_reference": "Text: EUR", "json_path": "StyleColor[0].SizeRegion.EUR"},
        {"id": "14", "pdf_reference": "Text: IT", "json_path": "StyleColor[0].SizeRegion.IT"},
        {"id": "15", "pdf_reference": "Text: UK", "json_path": "StyleColor[0].SizeRegion.UK"},
        {"id": "16", "pdf_reference": "Text: USA", "json_path": "StyleColor[0].SizeRegion.US"},
        {"id": "17", "pdf_reference": "Text: MEX", "json_path": "StyleColor[0].SizeRegion.MEX"},
        {"id": "18", "pdf_reference": "Text: CN", "json_path": "StyleColor[0].SizeRegion.CN"},
        {"id": "19", "pdf_reference": "Size: EUR", "json_path": "StyleColor[0].ItemData[#].SizeName"},
        {"id": "20", "pdf_reference": "Size: IT", "json_path": "StyleColor[0].ItemData[#].SizeNameIT"},
        {"id": "21", "pdf_reference": "Size: UK", "json_path": "StyleColor[0].ItemData[#].SizeNameUK"},
        {"id": "22", "pdf_reference": "Size: USA", "json_path": "StyleColor[0].ItemData[#].SizeNameUS"},
        {"id": "23", "pdf_reference": "Size: MEX", "json_path": "StyleColor[0].ItemData[#].SizeNameMX"},
        {"id": "24", "pdf_reference": "Size: CN", "json_path": "StyleColor[0].ItemData[#].SizeNameCN"},
        {"id": "25", "pdf_reference": "Family + Generic (ES)", "json_path": "StyleColor[0].ProductTypeES"},
        {"id": "26", "pdf_reference": "Layout text", "json_path": ""},
        {"id": "27", "pdf_reference": "Integer price ES (EUR)", "json_path": "StyleColor[0].PVP_ES"},
        {"id": "28", "pdf_reference": "Decimal price ES (EUR)", "json_path": "StyleColor[0].PVP_ES"},
        {"id": "29", "pdf_reference": "Special Size LEFT", "json_path": "StyleColor[0].Set"},
        {"id": "30", "pdf_reference": "Size Range", "json_path": "StyleColor[0].SizeRange[0].SizeName"},
        {"id": "31", "pdf_reference": "Special Size RIGHT", "json_path": ""},
        {"id": "32", "pdf_reference": "OPI MARK", "json_path": ""},
        {"id": "33", "pdf_reference": "Family + Generic (EN)", "json_path": "StyleColor[0].ProductType"},
        {"id": "34", "pdf_reference": "Integer price EU (EUR)", "json_path": "StyleColor[0].PVP_EU"},
        {"id": "35", "pdf_reference": "Decimal price EU (EUR)", "json_path": "StyleColor[0].PVP_EU"},
        {"id": "36", "pdf_reference": "Integer price IN (INR)", "json_path": "StyleColor[0].PVP_IN"},
        {"id": "37", "pdf_reference": "Decimal price IN (INR)", "json_path": "StyleColor[0].PVP_IN"},
        {"id": "38", "pdf_reference": "QR CODE URL", "json_path": ""},
        {"id": "39", "pdf_reference": "SAP CODE", "json_path": "StyleColor[0].ItemData[#].MangoSAPSizeCode"},
    ],
    "GI001BAW-GI001BAC": [
        {"id": "1", "pdf_reference": "ITEM DATATQTY", "json_path": "StyleColor[0].ItemData[#].itemQty"},
        {"id": "2", "pdf_reference": "Code of order.", "json_path": "LabelOrder.Id"},
        {"id": "3", "pdf_reference": "FAM CODE", "json_path": "StyleColor[0].ProductTypeCodeLegacy"},
        {"id": "4.0", "pdf_reference": "FAM LINE DESCRIPTION", "json_path": "StyleColor[0].Line"},
        {"id": "4.1", "pdf_reference": "FAM LINE DESCRIPTION", "json_path": "StyleColor[0].Age"},
        {"id": "4.2", "pdf_reference": "FAM LINE DESCRIPTION", "json_path": "StyleColor[0].Gender"},
        {"id": "5.1", "pdf_reference": "Reference number. First four digits", "json_path": "StyleColor[0].ReferenceID (first 4)"},
        {"id": "5.2", "pdf_reference": "Reference number. Last four digits", "json_path": "StyleColor[0].ReferenceID (last 4)"},
        {"id": "6", "pdf_reference": "The colour of the garment", "json_path": "StyleColor[0].MangoColorCode + \":\" + StyleColor[0].Color"},
        {"id": "7", "pdf_reference": "Size: EUR", "json_path": "StyleColor[0].ItemData[#].SizeNameES"},
        {"id": "8", "pdf_reference": "Family+Generic+code design text (Spanish)", "json_path": "StyleColor[0].ProductType + StyleColor[0].ProductTypeCodeLegacy + StyleColor[0].Generic"},
    ],
    "ADHEDIST-mango": [
        {"id": "1", "pdf_reference": "The quantity of labels to produce", "json_path": "StyleColor[0].ItemData[#].SizePack.TotalSizePackQty"},
        {"id": "2", "pdf_reference": "Code of supplier.", "json_path": "Supplier.SupplierCode"},
        {"id": "3", "pdf_reference": "Code of order.", "json_path": "LabelOrder.Id"},
        {"id": "4.1", "pdf_reference": "Reference number. First four digits", "json_path": "StyleColor[0].ReferenceID (first 4)"},
        {"id": "4.2", "pdf_reference": "Reference number. Last four digits", "json_path": "StyleColor[0].ReferenceID (last 4)"},
        {"id": "5", "pdf_reference": "The colour of the garment", "json_path": "StyleColor[0].MangoColorCode + \":\" + StyleColor[0].Color"},
        {"id": "6", "pdf_reference": "BAR CODE EAN ??13", "json_path": "StyleColor[0].ItemData[#].SizePack.SizeBarCode"},
        {"id": "7", "pdf_reference": "FAM CODE", "json_path": "StyleColor[0].ProductTypeCodeLegacy"},
        {"id": "8", "pdf_reference": "FAM LINE DESCRIPTION", "json_path": "StyleColor[0].Line"},
        {"id": "8.1", "pdf_reference": "DESCRIPTION", "json_path": "StyleColor[0].Age"},
        {"id": "8.2", "pdf_reference": "DESCRIPTION", "json_path": "StyleColor[0].Gender"},
        {"id": "9", "pdf_reference": "Size: EUR or empty", "json_path": "StyleColor[0].ItemData[#].SizeNameES"},
        {"id": "10", "pdf_reference": "size pack type", "json_path": "StyleColor[0].ItemData[#].SizePack.SizePackQty"},
        {"id": "11", "pdf_reference": "COUNTRY OF ORIGIN", "json_path": "StyleColor[0].Origin.countryorigin"},
        {"id": "12", "pdf_reference": "FAM DESCRIPTION", "json_path": "StyleColor[0].ProductType"},
        {"id": "13", "pdf_reference": "ICONIC", "json_path": "StyleColor[0].Iconic"},
    ],
}


# Mapping from template_name to the LabelID used in JSON order data
LABEL_ID_MAP: dict[str, str] = {
    "ADHEDIST-mango": "ADHEDIST",
    "GI000DPO-SAP_1": "GI000PRO",
    "GI001BAW-GI001BAC": "GI001BAW",
    "PVPV0102-PVP002XG": "PVP002XG",
}


def list_templates() -> list[dict]:
    """Return all available template names with field counts and grouping modes."""
    from labelforge.mappings import get_grouping_mode
    return [
        {
            "name": name,
            "field_count": len(fields),
            "label_id": LABEL_ID_MAP.get(name),
            "grouping_mode": get_grouping_mode(name),
        }
        for name, fields in LABEL_TEMPLATES.items()
    ]


def get_template_fields(template_name: str) -> list[dict] | None:
    """Return fields for a template, each augmented with field_type.

    Returns None if the template name is not found.
    """
    fields = LABEL_TEMPLATES.get(template_name)
    if fields is None:
        return None
    return [
        {
            "id": f["id"],
            "pdf_reference": f["pdf_reference"],
            "json_path": f["json_path"],
            "field_type": _classify_field(f["json_path"]),
        }
        for f in fields
    ]
