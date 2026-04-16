"""Excel translation lookup for label mappings.

Provides lazy loading and caching of translation data from TRANSLATIONS&RULES.xlsx.
Handles:
- MATERIALS: Fabric/material translations (33 languages)
- MADE IN COUNTRY: Country of origin translations (32 languages)
- TITLE: Composition title translations
- SAP-WASHING RULES: Care instruction translations (8 languages)
- GARMENT IMPORTERS: Importer text by country
- JSON-RULES: Rules for EAC, Triman, Korean symbols, French compliance text
"""

from __future__ import annotations

import openpyxl
from pathlib import Path
from typing import Any

# Path to the Excel file
_EXCEL_PATH = Path(__file__).parent / "TRANSLATIONS&RULES.xlsx"

# Cache for loaded sheets
_SHEET_CACHE: dict[str, list[tuple]] = {}

# Language order for multi-language output (per PDF spec)
LANGUAGE_ORDER = [
    # Front side languages
    "ENGLISH", "SPANISH", "SPANISH (MEXICO)", "CATALAN", "FRENCH", "GERMAN",
    "PORTUGuese", "ITALIAN", "EUSKERA", "GALICIAN", "DUTCH", "POLISH",
    "CZECH", "DANISH", "SLOVAK", "SLOVENIAN",
    # Back side languages
    "HUNGARIAN", "LATVIAN", "LITHUANIAN", "ROMANIAN", "GREEK", "RUSIAN",
    "BULGARIAN", "TURKISH", "INDONESIAN", "CHINESE", "KOREAN", "JAPANESE",
    "TAIWAN", "ARABIC",
]

# Sheet configurations: maps sheet name to code column index and language columns
SHEET_CONFIGS: dict[str, dict[str, Any]] = {
    "MATERIALS": {
        "code_col": 0,  # CODE
        "lang_cols": {
            "ENGLISH": 1,
            "SPANISH": 2,
            "SPANISH (MEXICO)": 3,
            "CATALAN": 4,
            "FRENCH": 5,
            "GERMAN": 6,
            "PORTUGuese": 7,
            "ITALIAN": 8,
            "EUSKERA": 9,
            "GALICIAN": 10,
            "DUTCH": 11,
            "POLISH": 12,
            "CZECH": 13,
            "DANISH": 14,
            "SLOVAK": 15,
            "SLOVENIAN": 16,
            "HUNGARIAN": 17,
            "LATVIAN": 18,
            "LITHUANIAN": 19,
            "ROMANIAN": 20,
            "GREEK": 21,
            "RUSIAN": 22,
            "BULGARIAN": 23,
            "TURKISH": 24,
            "INDONESIAN": 25,
            "FINNISH": 26,
            "SWEDISH": 27,
            "CHINESE": 28,
            "KOREAN": 29,
            "JAPANESE": 30,
            "TAIWAN": 31,
            "ARABIC": 32,
        },
    },
    "MADE IN COUNTRY": {
        "code_col": 1,  # CODE SAP (2-letter country code like MA, ES, etc.)
        "lang_cols": {
            "ENGLISH": 2,
            "SPANISH": 3,
            "CATALAN": 4,
            "PORTUGuese": 5,
            "FRENCH": 6,
            "GERMAN": 7,
            "DUTCH": 8,
            "HUNGARIAN": 9,
            "ITALIAN": 10,
            "ROMANIAN": 11,
            "LATVIAN": 12,
            "CZECH": 13,
            "LITHUANIAN": 14,
            "POLISH": 15,
            "DANISH": 16,
            "EUSKERA": 17,
            "GALICIAN": 18,
            "RUSIAN": 19,
            "GREEK": 20,
            "SLOVAK": 21,
            "SLOVENIAN": 22,
            "BULGARIAN": 23,
            "INDONESIAN": 24,
            "TURKISH": 25,
            "FINNISH": 26,
            "SWEDISH": 27,
            "CHINESE": 28,
            "TAIWANESE": 29,
            "KOREAN": 30,
            "JAPANESE": 31,
            "ARABIAN": 32,
        },
    },
    "TITLE": {
        "code_col": 0,  # CODE
        "lang_cols": {
            # Note: ENGLISH column is missing (index 1 is None)
            "SPANISH": 2,
            "FRENCH": 3,
            "CATALAN": 4,
            "GERMAN": 5,
            "PORTUGuese": 6,
            "ITALIAN": 7,
            "EUSKERA": 8,
            "GALICIAN": 9,
            "DUTCH": 10,
            "POLISH": 11,
            "CZECH": 12,
            "DANISH": 13,
            "SLOVAK": 14,
            "SLOVENIAN": 15,
            "HUNGARIAN": 16,
            "LATVIAN": 17,
            "LITHUANIAN": 18,
            "ROMANIAN": 19,
            "GREEK": 20,
            "RUSIAN": 21,
            "BULGARIAN": 22,
            "TURKISH": 23,
            "INDONESIAN": 24,
            "FINNISH": 25,
            "SWEDISH": 26,
            "CHINESE": 27,
            "KOREAN": 28,
            "JAPANESE": 29,
            "TAIWAN": 30,
            "ARABIC": 31,
        },
    },
    "SAP-WASHING RULES": {
        "code_col": 0,  # CODIGO SAP
        "lang_cols": {
            "ENGLISH": 1,
            "SPANISH": 2,
            "FRENCH": 3,
            "PORTUGuese": 4,
            "RUSIAN": 5,
            "INDONESIAN": 6,
            "TURKISH": 7,
        },
    },
}


def _load_sheet(sheet_name: str) -> list[tuple]:
    """Load a sheet and return all rows as tuples. Caches result."""
    if sheet_name in _SHEET_CACHE:
        return _SHEET_CACHE[sheet_name]

    wb = openpyxl.load_workbook(_EXCEL_PATH, read_only=True)
    ws = wb[sheet_name]

    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(tuple(row))

    wb.close()
    _SHEET_CACHE[sheet_name] = rows
    return rows


def translate(code: str, sheet: str, language: str = "SPANISH") -> str | None:
    """Translate a single code to a specific language.

    Args:
        code: The code to look up (e.g., "C005", "MA", "T001", "S02")
        sheet: Excel sheet name (e.g., "MATERIALS", "MADE IN COUNTRY")
        language: Target language (e.g., "SPANISH", "ENGLISH")

    Returns:
        Translated text or None if not found.
    """
    if not code:
        return None

    rows = _load_sheet(sheet)
    config = SHEET_CONFIGS.get(sheet, {})
    code_col = config.get("code_col", 0)
    lang_cols = config.get("lang_cols", {})

    # Normalize language name (handle variations)
    lang_key = language.upper().replace("-", " ").strip()
    if lang_key not in lang_cols:
        # Try fallback mappings
        lang_aliases = {
            "SPANISH": "SPANISH",
            "SPANISH MEXICO": "SPANISH (MEXICO)",
            "PORTUGuese": "PORTUGuese",
            "PORTUGUESE": "PORTUGuese",
            "RUSSIAN": "RUSIAN",
            "HUNGARIAN": "HUNGARIAN",
            "LATVIAN": "LATVIAN",
            "LITHUANIAN": "LITHUANIAN",
        }
        lang_key = lang_aliases.get(lang_key, "SPANISH")

    lang_col = lang_cols.get(lang_key, lang_cols.get("SPANISH", 1))

    # Search for matching code (case-insensitive)
    code_upper = str(code).strip().upper()
    for row in rows[1:]:  # Skip header row
        if row and len(row) > code_col and row[code_col]:
            row_code = str(row[code_col]).strip().upper()
            if row_code == code_upper:
                if len(row) > lang_col and row[lang_col]:
                    val = str(row[lang_col]).strip()
                    # Clean up non-breaking spaces
                    return val.replace("\xa0", " ")
                break

    return None


def translate_all_languages(
    code: str, sheet: str, separator: str = " / "  # noqa: ARG001
) -> dict[str, str]:
    """Get translations for a code in all available languages.

    Args:
        code: The code to look up
        sheet: Excel sheet name
        separator: Unused, kept for API compatibility

    Returns:
        Dict of {language: translated_text} for all languages in the sheet.
    """
    if not code:
        return {}

    rows = _load_sheet(sheet)
    config = SHEET_CONFIGS.get(sheet, {})
    code_col = config.get("code_col", 0)
    lang_cols = config.get("lang_cols", {})

    code_upper = str(code).strip().upper()
    result: dict[str, str] = {}

    for row in rows[1:]:
        if row and len(row) > code_col and row[code_col]:
            row_code = str(row[code_col]).strip().upper()
            if row_code == code_upper:
                for lang_name, lang_idx in lang_cols.items():
                    if len(row) > lang_idx and row[lang_idx]:
                        val = str(row[lang_idx]).strip().replace("\xa0", " ")
                        result[lang_name] = val
                break

    return result


def get_multi_language_string(
    code: str, sheet: str, separator: str = " / "
) -> str:
    """Get a concatenated string of translations in the standard language order.

    Args:
        code: The code to look up
        sheet: Excel sheet name
        separator: Separator between languages (default " / ")

    Returns:
        Concatenated string like "COTTON / ALGODÓN / COTON / ..."
    """
    translations = translate_all_languages(code, sheet)
    if not translations:
        return ""

    # Build string in language order
    parts = []
    for lang in LANGUAGE_ORDER:
        # Handle language name variations
        lang_key = lang
        if lang == "TAIWAN":
            lang_key = "TAIWAN" if "TAIWAN" in translations else "TAIWANESE"
        elif lang == "ARABIC":
            lang_key = "ARABIC" if "ARABIC" in translations else "ARABIAN"

        if lang_key in translations and translations[lang_key]:
            parts.append(translations[lang_key])

    return separator.join(parts) if parts else ""


# ---------------------------------------------------------------------------
# GARMENT IMPORTERS lookup
# ---------------------------------------------------------------------------

# Mapping from destination.dc or de_code to importer "Pais" column
DESTINATION_TO_IMPORTER: dict[str, str] = {
    "LLIÇÀ": "PUNTO FA",
    "D001": "PUNTO FA",
    "PUNTO FA": "PUNTO FA",
    "PERU": "PERU",
    "VENEZUELA": "VENEZUELA",
    "ECUADOR": "ECUADOR",
    "MEXICO": "MEXICO",
    "COLOMBIA": "COLOMBIA 1",
    "CHILE": "CHILE",
    "CANADA": "CANADA",
    "UK": "UK",
    "INDONESIA": "INDONESIA",
    "Marruecos": "Marruecos",
    "Argentina": "Argentina",
    "KOREA": "KOREA",
    "JAPON": "JAPON",
    "USA": "USA",
    "BRASIL": "BRASIL",
}


def get_importer_text(destination: str | None) -> str | None:
    """Get importer text for a destination.

    Args:
        destination: Destination code from JSON (dc or de_code)

    Returns:
        Importer text string or None.
    """
    if not destination:
        return None

    rows = _load_sheet("GARMENT IMPORTERS")

    # Map destination to Pais name
    pais = DESTINATION_TO_IMPORTER.get(destination.upper().strip())
    if not pais:
        # Try direct match
        pais = destination

    # Search for matching Pais (column 2)
    for row in rows[1:]:
        if row and len(row) > 3 and row[2]:
            row_pais = str(row[2]).strip()
            if row_pais.upper() == pais.upper():
                if len(row) > 3 and row[3]:
                    return str(row[3]).strip().replace("\xa0", " ")

    return None


# ---------------------------------------------------------------------------
# JSON-RULES lookup
# ---------------------------------------------------------------------------

# Mapping from JSON Line/Age to Excel DESC. GEN.
LINE_AGE_TO_DESC_GEN: dict[str, str] = {
    "WOMAN": "WOMAN",
    "MAN": "MAN",
    "KIDS": "KIDS GIRL",  # Need both BOY and GIRL
    "BABY": "BABY BOY",   # Need both BOY and GIRL
    "NEWBORN": "NEWBORN",
    "TEEN": "TEEN BOYS",  # Need both BOYS and GIRLS
    "HOME": "HOME",
}


def get_json_rules(
    desc_gen: str, fam_code: int | str, packaging: str
) -> dict[str, Any]:
    """Get rules from JSON-RULES sheet based on DESC. GEN., FAM_CODE, and PACKAGING.

    Args:
        desc_gen: Generic description/Line (e.g., "WOMAN", "MAN", "KIDS GIRL")
        fam_code: Family code (e.g., 208, 440)
        packaging: Packaging type (e.g., "FOLDED", "HANGER")

    Returns:
        Dict with:
            - italian_code: str | None
            - eac: int | None (1=EAC, 2=CH 01, None=none)
            - triman: str | None
            - french_text: str | None
            - korean_symbol: str | None
            - mca_law: str | None
    """
    rows = _load_sheet("JSON-RULES")

    # Normalize inputs
    desc_gen_upper = desc_gen.strip().upper() if desc_gen else ""
    fam_code_val = int(fam_code) if isinstance(fam_code, str) else fam_code
    packaging_upper = packaging.strip().upper() if packaging else ""

    result: dict[str, Any] = {
        "italian_code": None,
        "eac": None,
        "triman": None,
        "french_text": None,
        "korean_symbol": None,
        "mca_law": None,
    }

    # Search for matching row
    for row in rows[1:]:
        if not row or len(row) < 10:
            continue

        row_desc_gen = str(row[0]).strip().upper() if row[0] else ""
        row_fam_code = row[1] if row[1] is not None else None
        row_packaging = str(row[3]).strip().upper() if row[3] else ""

        # Match: DESC. GEN. (case-insensitive) + FAM_CODE + PACKAGING
        if row_desc_gen == desc_gen_upper:
            # Try to match FAM_CODE (int comparison)
            if row_fam_code is not None:
                try:
                    row_fam_int = int(row_fam_code)
                    if row_fam_int != fam_code_val:
                        continue
                except (ValueError, TypeError):
                    continue

            # Try to match PACKAGING (case-insensitive)
            if packaging_upper and row_packaging and row_packaging != packaging_upper:
                continue

            # Found match - extract values
            result["italian_code"] = row[4] if len(row) > 4 and row[4] else None
            result["eac"] = row[6] if len(row) > 6 and row[6] else None
            result["triman"] = row[7] if len(row) > 7 and row[7] else None
            result["french_text"] = row[8] if len(row) > 8 and row[8] else None
            result["korean_symbol"] = row[9] if len(row) > 9 and row[9] else None
            result["mca_law"] = row[10] if len(row) > 10 and row[10] else None

            # Clean up values
            for key, val in result.items():
                if isinstance(val, str):
                    result[key] = val.strip().replace("\xa0", "")
                    if not result[key]:
                        result[key] = None

            break

    return result


def get_rules_from_order(order_data: dict) -> dict[str, Any]:
    """Get rules by extracting parameters from order JSON.

    Args:
        order_data: Full order JSON (or StyleColor[0] dict)

    Returns:
        Rules dict from get_json_rules().
    """
    # Handle top-level array
    order = order_data[0] if isinstance(order_data, list) else order_data

    # Extract StyleColor[0] values
    style_color = order.get("StyleColor", [{}])[0] if "StyleColor" in order else order

    desc_gen = style_color.get("Line", "WOMAN")  # Line = WOMAN, MAN, KIDS, etc.
    fam_code = style_color.get("ProductTypeCodeLegacy", 0)
    packaging = style_color.get("Packaging", "FOLDED")

    # Map Line to DESC. GEN. (handle gender variations)
    line_upper = desc_gen.upper().strip()
    age = style_color.get("Age", "").upper().strip()
    gender = style_color.get("Gender", "").upper().strip()

    # Construct desc_gen for lookup
    if line_upper in ("KIDS", "KID"):
        if gender == "MALE" or age == "BOY":
            desc_gen = "KIDS BOY"
        else:
            desc_gen = "KIDS GIRL"
    elif line_upper in ("BABY",):
        if gender == "MALE" or age == "BOY":
            desc_gen = "BABY BOY"
        else:
            desc_gen = "BABY GIRL"
    elif line_upper in ("NEWBORN",):
        desc_gen = "NEWBORN"
    elif line_upper in ("TEEN",):
        if gender == "MALE":
            desc_gen = "TEEN BOYS"
        else:
            desc_gen = "TEEN GIRLS"
    elif line_upper in ("HOME",):
        desc_gen = "HOME"
    else:
        desc_gen = line_upper  # WOMAN, MAN

    return get_json_rules(desc_gen, fam_code, packaging)


# ---------------------------------------------------------------------------
# Russian age text (Zone G)
# ---------------------------------------------------------------------------

# Russian text templates based on SizeGroupLegacy and Line
RUSSIAN_AGE_TEXTS: dict[str, dict[str, str]] = {
    # SizeGroupLegacy 01 (Baby)
    "01": {
        "KIDS": "Возраст: от 4 до 14 лет",
        "BABY": "Возраст: от 3 месяцев до 3 лет",
        "NEWBORN": "Возраст: от 1 месяца до 12 месяцев",
    },
    # SizeGroupLegacy 82 (Kids)
    "82": {
        "KIDS": "Возраст: от 4 до 14 лет",
        "BABY": "Возраст: от 3 месяцев до 3 лет",
        "NEWBORN": "Возраст: от 1 месяца до 12 месяцев",
    },
    # SizeGroupLegacy 40 (Kids older)
    "40": {
        "KIDS": "Возраст: от 4 до 14 лет",
        "BABY": "Возраст: от 3 месяцев до 3 лет",
        "NEWBORN": "Возраст: от 1 месяца до 12 месяцев",
    },
}


def get_russian_age_text(size_group_legacy: str | None, line: str | None) -> str | None:
    """Get Russian age text for Zone G based on SizeGroupLegacy and Line.

    Args:
        size_group_legacy: Size group code (e.g., "01", "82", "40")
        line: Line value (e.g., "KIDS", "BABY", "NEWBORN")

    Returns:
        Russian age text or None.
    """
    if not size_group_legacy or not line:
        return None

    size_group = str(size_group_legacy).strip()
    line_upper = line.upper().strip()

    # Get text from lookup
    group_texts = RUSSIAN_AGE_TEXTS.get(size_group)
    if group_texts:
        return group_texts.get(line_upper)

    return None