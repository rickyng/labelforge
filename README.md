# LabelForge

A professional CLI tool for high-fidelity PDF and Adobe Illustrator (.ai) text label editing.

**Extract → Edit → Re-apply** — without touching anything else in your document.

## Why LabelForge?

Most PDF text-editing approaches re-render the entire document, losing fonts, image
compression, vector quality, and searchability. LabelForge uses a **redact-then-insert**
strategy:

1. `page.apply_redactions()` erases *only* the pixels under the changed span.
2. New text is inserted as real Unicode glyphs — fully searchable.
3. Everything else (images, paths, other text, metadata) is untouched.

Result: smaller output file, pixel-perfect quality preservation.

### Adobe Illustrator (.ai) Support

Modern `.ai` files contain an embedded PDF compatibility layer. LabelForge opens this
layer directly via PyMuPDF — no Illustrator installation required.

**Limitations to be aware of:**
- Only text spans are extracted and edited. Background vectors, paths, gradients,
  symbols, and effects are preserved in the output but cannot be modified.
- Saving back as `.ai` produces a PDF file with a `.ai` extension — it is **not** a
  true native Illustrator file. For full Illustrator compatibility, open the output
  in Illustrator and use **File > Save As > Adobe Illustrator (.ai)**.
- For best results, export your `.ai` to PDF first in Illustrator
  (**File > Save As > PDF**, uncheck *Preserve Illustrator Editing Capabilities*)
  before running LabelForge.

---

## Installation

### Using uv (recommended)

```bash
git clone <repo>
cd pdf
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Using pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Workflow

### PDF Workflow

#### Step 1 — Extract labels

```bash
labelforge analyze invoice.pdf --output labels.json
```

This produces a `labels.json` with every text span in the PDF.

#### Step 2 — Edit the JSON

Open `labels.json` in any editor. Find the spans you want to change and set `new_text`:

```json
{
  "id": "p0_b2_l1_s0",
  "page": 0,
  "bbox": [72.0, 680.5, 300.0, 694.5],
  "original_text": "ACME Corporation",
  "new_text": "Globex Industries",
  "fontname": "Helvetica-Bold",
  "fontsize": 12.0,
  "color": "#1a1a1a",
  "flags": 16,
  "rotation": 0,
  "block_index": 2,
  "line_index": 1,
  "span_index": 0
}
```

- Leave `new_text` as `null` to skip a label.
- Set `new_text` to `""` to erase the span with no replacement.

#### Step 3 — Apply edits

```bash
labelforge apply invoice.pdf labels.json --output invoice_edited.pdf
```

---

### Adobe Illustrator (.ai) Workflow

#### Step 1 — Extract labels from .ai

```bash
labelforge analyze design.ai --output labels.json
```

LabelForge reads the embedded PDF layer of the `.ai` file and extracts all text spans.
A compatibility warning is shown — this is expected.

#### Step 2 — Edit the JSON

Open `labels.json` and set `new_text` on the labels you want to change:

```json
{
  "id": "p0_b5_l2_s0",
  "original_text": "MADE IN HONG KONG",
  "new_text": "MADE IN JAPAN"
}
```

Leave all other fields unchanged. Labels with `new_text: null` are skipped.

#### Step 3a — Output as PDF (recommended)

Preserves all original artwork. Only the changed text spans are replaced.

```bash
labelforge apply design.ai labels.json --output design_edited.pdf --force
```

#### Step 3b — Output as .ai

Produces a PDF file with a `.ai` extension. All original artwork is preserved.
Open the result in Illustrator and use **File > Save As > Adobe Illustrator (.ai)**
to get a true native `.ai` file.

```bash
labelforge apply design.ai labels.json --output design_edited.ai --output-format ai --force
```

#### Step 3c — Build from JSON only (no source file)

If the original `.ai` or `.pdf` is unavailable, you can generate a PDF containing
only the text labels on a blank white page:

```bash
labelforge build labels.json --output labels_only.pdf --force
```

> **Note:** Background graphics and vectors are not included in `build` output.

---

## Command Reference

### `labelforge analyze`

Accepts `.pdf` or `.ai` input.

```
Usage: labelforge analyze INPUT [OPTIONS]

Options:
  -o, --output PATH          Destination labels JSON file  [default: labels.json]
  --pretty / --compact       Pretty-print JSON output      [default: pretty]
  -m, --min-font-size FLOAT  Skip spans smaller than this (pt)  [default: 0.0]
  -p, --page TEXT            Page range e.g. '0-5' or '0,2,4'. Default: all
  -v, --verbose              Enable debug logging
```

**Examples:**

```bash
# Analyze a PDF
labelforge analyze report.pdf

# Analyze an .ai file
labelforge analyze design.ai --output labels.json

# Pages 0–4 only, minimum 8pt font, compact JSON
labelforge analyze report.pdf -o report_labels.json -p 0-4 -m 8 --compact
```

### `labelforge apply`

Accepts `.pdf` or `.ai` input. Outputs PDF by default; use `--output-format ai`
to save with a `.ai` extension (content is still PDF — see .ai limitations above).

```
Usage: labelforge apply INPUT LABELS_JSON [OPTIONS]

Options:
  -o, --output PATH           Destination file           [default: output.pdf]
  --output-format [pdf|ai]    Output format              [default: pdf]
  -b, --backup                Copy input to <input>.bak before writing
  -f, --force                 Overwrite output if it already exists
  -v, --verbose               Enable debug logging
```

**Examples:**

```bash
# Apply edits to a PDF
labelforge apply report.pdf labels.json -o report_v2.pdf

# Apply edits to an .ai, output as PDF (preserves all artwork)
labelforge apply design.ai labels.json --output design_edited.pdf --force

# Apply edits to an .ai, output as .ai
labelforge apply design.ai labels.json --output design_edited.ai --output-format ai --force
```

### `labelforge build`

Create a new PDF from a labels JSON file without a source document.
Useful when the original file is unavailable. Background graphics are not included.

```
Usage: labelforge build LABELS_JSON [OPTIONS]

Options:
  -o, --output PATH  Destination PDF file  [default: output.pdf]
  -f, --force        Overwrite output if it already exists
  -v, --verbose      Enable debug logging
```

**Examples:**

```bash
labelforge build labels.json --output labels_only.pdf --force
```

### `labelforge convert`

Convert an `.ai` file to PDF.

```
Usage: labelforge convert INPUT [OPTIONS]

Options:
  --to TEXT          Output format (currently only 'pdf')  [default: pdf]
  -o, --output PATH  Destination file
  -f, --force        Overwrite output if it already exists
  -v, --verbose      Enable debug logging
```

**Examples:**

```bash
labelforge convert design.ai --to pdf --output design.pdf
```

### `labelforge replace`

Inline replacement — no JSON file needed:

```
Usage: labelforge replace INPUT_PDF OLD_TEXT NEW_TEXT [OPTIONS]

Options:
  -o, --output PATH  Destination PDF file  [default: output.pdf]
  -p, --page TEXT    Limit to page range
  -a, --all          Replace all occurrences (default: first only)
  -f, --force        Overwrite output if it already exists
```

**Examples:**

```bash
# Replace first occurrence
labelforge replace contract.pdf "Draft" "FINAL" -o contract_final.pdf

# Replace all, page 0 only
labelforge replace contract.pdf "v1.0" "v2.0" --all --page 0 -o contract_v2.pdf
```

---

## JSON Schema

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique ID: `p<page>_b<block>_l<line>_s<span>` |
| `page` | int | 0-based page index |
| `bbox` | [x0, y0, x1, y1] | Span bounding box in points (top-left origin) |
| `original_text` | string | Text as extracted from PDF |
| `new_text` | string \| null | `null`=skip, `""`=erase, string=replace |
| `fontname` | string | Font name from PDF |
| `fontsize` | float | Font size in points |
| `color` | string | Text color as `#rrggbb` |
| `flags` | int | Font flags bitmask (bold=16, italic=2) |
| `rotation` | int | Page rotation in degrees |
| `block_index` | int | Block index within page |
| `line_index` | int | Line index within block |
| `span_index` | int | Span index within line |

---

## Coordinate System

PyMuPDF uses a **top-left origin** internally (y=0 at top, increases downward).
`get_text("dict")` returns bboxes in this system, and `insert_textbox` consumes
the same system. No coordinate conversion is needed — bbox values can be used directly.

> Note: Some PyMuPDF documentation shows a "PDF bottom-left" coordinate system.
> That applies to raw PDF operators, not to the Python API used by LabelForge.

---

## Font Fallback Strategy

When the original PDF font is not a PyMuPDF built-in, LabelForge maps it to the
closest available built-in:

| Condition | Built-in key | Name |
|---|---|---|
| Helvetica / Arial family | `helv` | Helvetica |
| Helvetica Bold | `hebo` | Helvetica Bold |
| Helvetica Italic/Oblique | `heit` | Helvetica Oblique |
| Helvetica Bold Italic | `hebi` | Helvetica Bold Oblique |
| Times family | `tiro` | Times Roman |
| Times Bold | `tibo` | Times Bold |
| Times Italic | `tiit` | Times Italic |
| Times Bold Italic | `tibi` | Times Bold Italic |
| Courier family | `cour` | Courier |
| Courier Bold | `cobo` | Courier Bold |
| Symbol | `symb` | Symbol |
| ZapfDingbats | `zadb` | ZapfDingbats |
| Default fallback | `helv` | Helvetica |

Subset prefixes (`ABCDEF+FontName`) are stripped before matching.

---

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=labelforge --cov-report=term-missing

# Lint
ruff check labelforge tests

# Type check
mypy labelforge
```

---

## Future Extensions (Phase 2+)

- **FastAPI web backend** — REST API for programmatic label editing
- **React frontend** — visual overlay editor with bbox highlighting
- **OCR integration** — label support for scanned/image-based PDFs
- **Batch processing** — process entire directories of PDFs
- **Font embedding** — embed custom TTF/OTF fonts for exact font matching
