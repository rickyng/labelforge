# LabelForge CLI Commands

Install the package first (from project root):

```bash
pip install -e ".[web]"
```

Then invoke with:

```bash
labelforge <command> [options]
```

---

## Recommended Workflow (components pipeline)

```bash
# 1. Extract all components (text, images, barcodes, shapes)
labelforge components artwork.ai -o components.json

# 2. Edit components.json or have the UI write a changes file:
#    changes.json = { "<component_id>": "new value", ... }  (only changed items)

# 3. Apply changes — source path is embedded in components.json, no extra arg needed
labelforge apply --components components.json --changes changes.json -o output.pdf
```

---

## Global Options

| Flag | Short | Description |
|------|-------|-------------|
| `--version` | `-V` | Print version and exit |
| `--help` | | Show help for any command |

---

## Commands

### `components`

Extract all component types (text, images, barcodes, shapes) from a PDF or `.ai` file.
The output JSON embeds the source file path so `apply --components` needs no separate input file.
Barcode values are decoded automatically if `libzbar` is installed.

```bash
labelforge components INPUT_FILE [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `components.json` | Destination JSON file |
| `--types LIST` | `-t` | all | Comma-separated types: `TEXT,IMAGE,BARCODE,SHAPE` |
| `--pretty / --compact` | | `--pretty` | Pretty-print or compact JSON |
| `--verbose` | `-v` | off | Enable debug logging |

**Prerequisites for barcode detection:**
- macOS: `brew install zbar`
- Linux/Docker: `apt install libzbar0`

**Output format (`components.json`):**
```json
{
  "source_file": "/abs/path/to/input.ai",
  "components": [
    {
      "id": "p0_t_b0_l0_s0",
      "type": "TEXT",
      "page": 0,
      "bbox": [x0, y0, x1, y1],
      "text": "Original text",
      "fontname": "Helvetica",
      "fontsize": 12.0,
      "color": "#000000",
      "flags": 0,
      "rotation": 0,
      "origin": [x, y]
    },
    ...
  ]
}
```

**Example:**
```bash
# Extract everything
labelforge components artwork.ai -o components.json

# Extract barcodes only
labelforge components artwork.ai --types BARCODE -o barcodes.json
```

---

### `apply`

Apply changes to a PDF or `.ai` file.

**New mode (recommended) — uses components.json + changes.json:**

```bash
labelforge apply --components components.json --changes changes.json -o out.pdf
```

`changes.json` is a minimal map of component IDs to new values:
```json
{
  "p0_t_b0_l0_s0": "Replacement text",
  "p0_vbarcode_0": "012345678905"
}
```
Only components that differ from the original need to be listed.
The source file path is read from `components.json` — no separate input file argument.

**Legacy mode (deprecated) — uses labels JSON:**

```bash
labelforge apply INPUT_PDF LABELS_JSON -o out.pdf
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--components PATH` | `-c` | | `components.json` from `labelforge components` (new mode) |
| `--changes PATH` | | | `changes.json` mapping component ID to new value (new mode) |
| `--output PATH` | `-o` | `output.pdf` | Destination PDF file |
| `--backup` | `-b` | off | Copy input to `<input>.bak` before writing |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--output-format FORMAT` | | `pdf` | Output format: `pdf` or `ai` (legacy mode only) |
| `--verbose` | `-v` | off | Enable debug logging |

**Examples:**
```bash
# New mode
labelforge apply --components components.json --changes changes.json -o output.pdf --force

# Legacy mode
labelforge apply invoice.pdf labels.json -o invoice_edited.pdf --force
```

---

### `analyze` _(deprecated)_

> **Deprecated.** Use `labelforge components` instead, which covers all component
> types and feeds the `apply --components` workflow.

Extract all text spans from a PDF or `.ai` file into a labels JSON file.

```bash
labelforge analyze INPUT_PDF [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `labels.json` | Destination labels JSON file |
| `--pretty / --compact` | | `--pretty` | Pretty-print or compact JSON |
| `--min-font-size FLOAT` | `-m` | `0.0` | Skip spans smaller than this size (pt) |
| `--page RANGE` | `-p` | all | Page range, e.g. `0-5` or `0,2,4` |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge analyze invoice.pdf -o labels.json --page 0-2
```

---

### `replace`

Inline replacement: find `OLD_TEXT` in a PDF and replace with `NEW_TEXT`.
Skips the JSON step — useful for quick one-off edits.

```bash
labelforge replace INPUT_PDF OLD_TEXT NEW_TEXT [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `output.pdf` | Destination PDF file |
| `--page RANGE` | `-p` | all | Limit to page range |
| `--all` | `-a` | off | Replace all occurrences (default: first only) |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge replace label.pdf "Draft" "Final" -o label_final.pdf --all
```

---

### `build`

Build a new PDF from a labels JSON file without a source document.
Places every label at its original bbox on a blank white page.
Background graphics and vectors from the original are not included.

```bash
labelforge build LABELS_JSON [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `output.pdf` | Destination PDF file |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge build labels.json -o rebuilt.pdf
```

---

### `convert`

Convert an `.ai` or PDF file to a plain PDF.

```bash
labelforge convert INPUT_FILE [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--to FORMAT` | | `pdf` | Output format. Only `pdf` is supported currently |
| `--output PATH` | `-o` | `<input>.pdf` | Destination PDF file |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge convert artwork.ai -o artwork.pdf --force
```

---

### `inspect`

Display all labels from a labels JSON file in a formatted table.

```bash
labelforge inspect LABELS_JSON [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--changed-only` | `-c` | off | Show only labels with `new_text` set |

**Example:**
```bash
labelforge inspect labels.json --changed-only
```

---

## Helper Scripts

### `generate_changes.py`

Generates per-size `changes.json` files from a Mango label order JSON and a `components.json`.
Useful for batch label production where one order produces many size variants.

```bash
python generate_changes.py \
    --order   4500801837-00000017-205456MK26.json \
    --components check_components.json \
    --out-dir changes/
```

Outputs one `changes.json` per size entry found in the order, e.g.:
```
changes/205456MK26_01_XXS.json
changes/205456MK26_01_XS.json
changes/205456MK26_01_S.json
...
```

Each file is a flat `{component_id: new_value}` dict ready for `labelforge apply`:

```bash
labelforge apply \
    --components check_components.json \
    --changes changes/205456MK26_01_XXS.json \
    --output out/label_XXS.pdf
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--order PATH` | | required | Mango order JSON file |
| `--components PATH` | | required | `components.json` from `labelforge components` |
| `--out-dir DIR` | | `changes/` | Directory to write per-size output files |
| `--verbose` | `-v` | off | Print detected roles and per-size change maps |

**Field roles auto-detected from component text:**

| Role | Pattern matched |
|---|---|
| `EAN13` | 13-digit barcode string |
| `SIZE` | XXS / XS / S / M / L / XL / XXL / XXXL / numeric |
| `UNITS` | 1–5 digit integer |
| `REF` | Starts with `REF:` or `REF ` |
| `COLOR_CODE` | Starts with `C:` or `C ` followed by digits |
| `ORIGIN` | Starts with `Made in` |
| `PO_ID` | 10-digit integer |
| `STYLE_ID` | 6–12 char alphanumeric |
| `SEASON` | SS or AW followed by 4-digit year |
| `ICONIC` | Literal `iconic` |

---

## Which command should I use?

| Goal | Command |
|------|---------|
| Extract all components for UI/automation | `components` |
| Apply changes from UI or script | `apply --components … --changes …` |
| Quick one-off text swap | `replace` |
| Rebuild PDF from labels without source | `build` |
| Convert `.ai` to PDF | `convert` |
| Inspect a legacy labels JSON | `inspect` |
| (Legacy) text-only extraction | `analyze` _(deprecated)_ |
