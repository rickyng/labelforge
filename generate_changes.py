#!/usr/bin/env python3
"""Generate changes.json files from a Mango label order JSON + a components.json.

Usage:
    python generate_changes.py \
        --order   4500801837-00000017-205456MK26.json \
        --components check_components.json \
        --out-dir changes/

Outputs one changes.json per size (ItemData entry), e.g.:
    changes/205456MK26_01_XXS.json
    changes/205456MK26_01_XS.json
    ...

Each file is a flat {component_id: new_value} dict ready for:
    labelforge apply --components check_components.json \
                     --changes changes/205456MK26_01_XXS.json \
                     --output out/label_XXS.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Field classifier — maps component text to semantic role
# ---------------------------------------------------------------------------

# Patterns that identify a component as carrying a specific data field.
# Order matters: more specific patterns first.
_FIELD_PATTERNS: list[tuple[str, str]] = [
    # EAN-13 barcode text or barcode component value
    (r"^\d{13}$", "EAN13"),
    # Size label — common Mango size labels
    (r"^(XXS|XS|S|M|L|XL|XXL|XXXL|1XL|2XL|3XL|4XL|\d{2,3})$", "SIZE"),
    # Units / quantity — small integer alone
    (r"^\d{1,5}$", "UNITS"),
    # REF line (e.g. "REF: 2100 1235" or "REF:2100")
    (r"(?i)^ref[: ]", "REF"),
    # Color code line (e.g. "C:01" or "C: 01")
    (r"(?i)^c[: ]\d+", "COLOR_CODE"),
    # Made in / country of origin
    (r"(?i)^made in ", "ORIGIN"),
    # PO / order number (10-digit)
    (r"^\d{10}$", "PO_ID"),
    # Style / reference ID (alphanumeric, 6-12 chars)
    (r"^[A-Z0-9]{6,12}$", "STYLE_ID"),
    # Season code (e.g. SS2026, AW2025)
    (r"(?i)^(SS|AW)\d{4}$", "SEASON"),
    # ICONIC label
    (r"(?i)^iconic$", "ICONIC"),
]


def classify(text: str) -> str | None:
    """Return the semantic role for a text value, or None if unknown."""
    t = text.strip()
    for pattern, role in _FIELD_PATTERNS:
        if re.match(pattern, t):
            return role
    return None


# ---------------------------------------------------------------------------
# Build a component index from components.json
# ---------------------------------------------------------------------------

def load_components(path: Path) -> list[dict]:
    with path.open() as f:
        data = json.load(f)
    # Support both bare list (check_components.json) and wrapped {source_file, components}
    if isinstance(data, list):
        return data
    return data.get("components", [])


def build_component_index(components: list[dict]) -> dict[str, list[dict]]:
    """Group components by their semantic role."""
    index: dict[str, list[dict]] = {}
    for comp in components:
        text = (comp.get("text") or "").strip()
        comp_type = comp.get("type", "")
        if comp_type == "BARCODE":
            role = "EAN13"
        elif comp_type == "TEXT" and text:
            role = classify(text)
        else:
            role = None
        if role:
            index.setdefault(role, []).append(comp)
    return index


# ---------------------------------------------------------------------------
# Build changes dict for one size (one ItemData entry)
# ---------------------------------------------------------------------------

def build_changes(
    style: dict,
    item: dict,
    order: dict,
    index: dict[str, list[dict]],
    verbose: bool = False,
) -> dict[str, str]:
    """Return a {component_id: new_value} mapping for one ItemData size."""
    changes: dict[str, str] = {}

    def assign(role: str, value: str, slot: int = 0) -> None:
        comps = index.get(role, [])
        if slot < len(comps):
            cid = comps[slot]["id"]
            changes[cid] = value
            if verbose:
                print(f"  [{role}] {cid} <- {repr(value)}")
        else:
            if verbose:
                print(f"  [{role}] WARNING: no component at slot {slot} (value={repr(value)})")

    # --- EAN13 barcode(s) ---
    ean = item.get("EAN13", "")
    assign("EAN13", ean, slot=0)

    # --- Size ---
    assign("SIZE", item.get("SizeName", ""), slot=0)

    # --- Units / quantity ---
    assign("UNITS", item.get("itemQty", ""), slot=0)

    # --- Color code (e.g. C:01) ---
    color_code = f"C:{item.get('MangoColorCode', style.get('MangoColorCode', ''))}"
    assign("COLOR_CODE", color_code, slot=0)

    # --- Country of origin ---
    country = style.get("Origin", {}).get("countryorigin", "")
    assign("ORIGIN", f"MADE IN {country.upper()}", slot=0)

    # --- REF line ---
    style_id = style.get("StyleID", "")
    sap_size = item.get("MangoSAPSizeCode", "")
    assign("REF", f"REF: {style_id} {sap_size}".strip(), slot=0)

    # --- PO / Order ID ---
    assign("PO_ID", order.get("Id", ""), slot=0)

    # --- Style ID (standalone) ---
    assign("STYLE_ID", style_id, slot=0)

    # --- Season ---
    assign("SEASON", order.get("Temporada", ""), slot=0)

    # --- ICONIC (keep or clear based on flag) ---
    is_iconic = style.get("Iconic", "NO").upper() == "YES"
    assign("ICONIC", "ICONIC" if is_iconic else "", slot=0)

    return changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate changes.json files from a Mango order JSON.")
    parser.add_argument("--order", required=True, type=Path, help="Path to the Mango order JSON file.")
    parser.add_argument("--components", required=True, type=Path, help="Path to the components.json file.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Directory to write changes files into.")
    parser.add_argument("--style-index", type=int, default=0, help="Which StyleColor entry to use (default: 0).")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print mapping details.")
    args = parser.parse_args()

    # Load order JSON
    with args.order.open() as f:
        raw = json.load(f)
    if isinstance(raw, list):
        raw = raw[0]  # unwrap top-level array

    label_order = raw.get("LabelOrder", raw)
    style_colors = raw.get("StyleColor", [])
    if not style_colors:
        print("ERROR: No StyleColor entries found in order JSON.", file=sys.stderr)
        sys.exit(1)

    style = style_colors[args.style_index]
    items = style.get("ItemData", [])
    if not items:
        print("ERROR: No ItemData entries found in StyleColor.", file=sys.stderr)
        sys.exit(1)

    # Load components and build index
    components = load_components(args.components)
    index = build_component_index(components)

    if args.verbose:
        print(f"Components loaded: {len(components)}")
        print(f"Roles detected: {list(index.keys())}")
        print(f"StyleColor: {style.get('StyleID')} / {style.get('Color')}")
        print(f"ItemData entries: {len(items)}")
        print()

    # Generate one changes.json per size
    args.out_dir.mkdir(parents=True, exist_ok=True)
    style_id = style.get("StyleID", "unknown")
    color_code = style.get("MangoColorCode", "00")

    generated = []
    for item in items:
        size_name = item.get("SizeName", "UNK").replace("/", "-")
        out_file = args.out_dir / f"{style_id}_{color_code}_{size_name}.json"

        if args.verbose:
            print(f"--- {size_name} ---")

        changes = build_changes(style, item, label_order, index, verbose=args.verbose)
        with out_file.open("w") as f:
            json.dump(changes, f, indent=2, ensure_ascii=False)
        generated.append(out_file)

        if args.verbose:
            print()

    print(f"Generated {len(generated)} changes file(s) in {args.out_dir}/")
    for p in generated:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
