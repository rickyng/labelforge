# LabelForge

A professional PDF and Adobe Illustrator (.ai) text label editor — available as both a **CLI tool** and a **web application**.

**Extract → Edit → Re-apply** — without touching anything else in your document.

## Why LabelForge?

Most PDF text-editing approaches re-render the entire document, losing fonts, image compression, vector quality, and searchability. LabelForge uses a **redact-then-insert** strategy:

1. `page.apply_redactions()` erases *only* the pixels under the changed span.
2. New text is inserted as real Unicode glyphs — fully searchable.
3. Everything else (images, paths, other text, metadata) is untouched.

Result: smaller output file, pixel-perfect quality preservation.

### Adobe Illustrator (.ai) Support

Modern `.ai` files contain an embedded PDF compatibility layer. LabelForge opens this layer directly via PyMuPDF — no Illustrator installation required.

**Limitations:**
- Only text spans are extracted and edited. Background vectors, paths, gradients, symbols, and effects are preserved but cannot be modified.
- Saving back as `.ai` produces a PDF file with a `.ai` extension — not a true native Illustrator file.
- For best results, export your `.ai` to PDF first in Illustrator (**File > Save As > PDF**, uncheck *Preserve Illustrator Editing Capabilities*) before running LabelForge.

---

## Architecture

```
labelforge/            ← project root
├── labelforge/        ← core library (CLI + Python API)
│   └── mappings/     ← auto-discovered template registry (one file per label type)
├── backend/           ← FastAPI web server
├── frontend/          ← React + Vite web UI
└── tests/
```

**Development mode** (two processes):
```
React + Vite (port 5173)  →  proxies /api  →  FastAPI (port 8000)
```

**Production / Docker** (single process, single port):
```
FastAPI (port 8000)
  /api/*          — REST API
  /assets/*       — built frontend static files
  /*              — SPA index.html fallback

Routes:
  /login  — authentication
  /admin  — full label editor (bbox, font, color controls)
  /user   — text-only replacement form
```

---

## Quick Start

### Docker (recommended)

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Compose

```bash
git clone <repo> && cd labelforge
make docker-build   # build image (first time or after code changes)
make docker-up      # start at http://localhost:8000
```

Open http://localhost:8000 — login with `admin/admin123` or `user/user123`.

```bash
make docker-logs    # tail logs
make docker-down    # stop
make docker-clean   # stop + wipe database volume
```

### Local development

**Prerequisites:** Python ≥ 3.11, Node.js ≥ 18

```bash
git clone <repo> && cd labelforge
make setup   # one-time: creates venv, installs all deps
make dev     # starts backend :8000 + frontend :5173
```

Open http://localhost:5173 — login with `admin/admin123` or `user/user123`.

Run `make help` to see all available commands.

### Manual setup (without make)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,dev]"
cd frontend && npm install && cd ..

# Terminal 1
uvicorn backend.main:app --reload --port 8000
# Terminal 2
cd frontend && npm run dev
```

---

## CLI Usage

### Recommended Workflow (components pipeline)

The components pipeline extracts all component types (text, images, barcodes, shapes) and embeds the source file path in the output — so `apply` needs no separate input file argument.

```bash
# 1. Extract all components
labelforge components artwork.ai -o components.json

# 2. Build a changes file (flat {component_id: new_value} map)
#    Use generate_changes.py (for Mango order JSON) or edit manually.

# 3. Apply
labelforge apply --components components.json --changes changes.json -o output.pdf
```

---

### Legacy Workflow (text-only, labels pipeline)

Still supported but `analyze` is deprecated in favour of `components`.

#### Step 1 — Extract text spans

```bash
labelforge analyze invoice.pdf --output labels.json
```

#### Step 2 — Edit labels.json

Set `new_text` on spans you want to change:

```json
{
  "id": "p0_b2_l1_s0",
  "original_text": "ACME Corporation",
  "new_text": "Globex Industries"
}
```

- Leave `new_text` as `null` to skip.
- Set `new_text` to `""` to erase only.

#### Step 3 — Apply

```bash
labelforge apply invoice.pdf labels.json --output invoice_edited.pdf
```

---

### CLI Reference

#### `labelforge components` _(recommended)_

```
Usage: labelforge components [OPTIONS] INPUT_FILE

Options:
  --output FILE         Destination JSON file (default: components.json)
  --types LIST          Comma-separated: TEXT,IMAGE,BARCODE,SHAPE (default: all)
  --pretty / --compact  Pretty-print or compact JSON (default: pretty)
  --verbose             Enable debug logging
  --help
```

#### `labelforge apply`

```
# Components mode (recommended)
Usage: labelforge apply [OPTIONS] --components FILE --changes FILE

# Legacy mode
Usage: labelforge apply [OPTIONS] INPUT_FILE LABELS_FILE

Options:
  --output FILE           Output file path (required)
  --force                 Overwrite existing output file
  --white-out             Fill bounding box with white before inserting text
  --padding FLOAT         Inset the insertion rect by FLOAT pt on each side
  --max-scale-down FLOAT  Minimum font scale factor for auto-fit (0.0–1.0)
  --help
```

#### `labelforge analyze` _(deprecated — use `components`)_

```
Usage: labelforge analyze [OPTIONS] INPUT_FILE

Options:
  --output FILE       Write labels JSON to FILE (default: stdout)
  --pages TEXT        Page range, e.g. "1", "1-3", "1,3,5" (1-based)
  --min-fontsize NUM  Exclude spans smaller than NUM pt (default: 0)
  --no-warn           Suppress .ai compatibility warning
  --help
```

---

## Web Interface

### Starting the servers

```bash
# Terminal 1 — backend (from project root)
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

### Login credentials

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | `admin`  | `admin123` |
| User  | `user`   | `user123`  |

### Admin interface (`/admin`)

- Full PDF preview via PDF.js
- All extracted labels displayed with editable fields:
  - `new_text` replacement
  - Bounding box (`x0`, `y0`, `x1`, `y1`) — also draggable on the PDF canvas overlay
  - Font size and color picker
  - `auto_fit`, `white_out`, `max_scale_down`, `padding` toggles
- Output format selector: **PDF** or **.ai** (with warning)
- "Apply All Changes" → generates output → download button

### User interface (`/user`)

- Same PDF preview
- Simple form: one text input per label (text replacement only)
- No position, font, or overflow controls exposed
- "Generate Updated File" → PDF output only

---

## Web API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/login` | Login, sets `role` cookie |
| `POST` | `/api/auth/logout` | Clear cookies |
| `POST` | `/api/upload` | Upload `.pdf` or `.ai` file |
| `POST` | `/api/analyze/{sid}` | Extract labels from uploaded file |
| `POST` | `/api/apply/{sid}` | Apply label edits, produce output |
| `GET`  | `/api/preview/{sid}` | Stream PDF for preview |
| `GET`  | `/api/download/{sid}` | Download output file |
| `GET`  | `/api/configs` | List saved label configs |
| `GET/PATCH/DELETE` | `/api/configs/{name}` | Manage a saved config |
| `POST` | `/api/editable/{sid}` | Set editable label IDs for user role |
| `GET/POST/DELETE` | `/api/labels/{name}` | Manage user label presets |

---

## Label JSON Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique span ID (`p{page}_b{block}_l{line}_s{span}`) |
| `page` | int | 0-based page index |
| `bbox` | [x0, y0, x1, y1] | Bounding box in pt (top-left origin) |
| `original_text` | string | Extracted text |
| `new_text` | string \| null | Replacement text (`null` = skip) |
| `fontname` | string | Original font name |
| `fontsize` | float | Font size in pt |
| `color` | string | Hex color (`#rrggbb`) |
| `flags` | int | PyMuPDF font flags bitmask |
| `rotation` | int | Page rotation in degrees |

---

## Coordinate System

PyMuPDF uses a **top-left origin** (y=0 at top, increases downward). `get_text("dict")` returns bboxes in this system and `insert_textbox` consumes the same system. No coordinate conversion needed.

---

## Font Resolution Strategy

When inserting replacement text, LabelForge resolves the font in this order:

1. **Embedded font from source document** — extracts the raw font bytes already embedded in the PDF/AI file and reuses them directly. This preserves the exact original typeface with no system font installation required.
2. **System font file** — looks up the font name against a table of known paths on macOS (`/System/Library/Fonts/Supplemental/`) and Linux (`/usr/share/fonts/truetype/msttcorefonts/`). Covers Arial, Times New Roman, and Courier New variants.
3. **PyMuPDF built-in** — maps the font name to the closest base-14 equivalent:

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
make test        # run pytest
make test-cov    # pytest with coverage
make lint        # ruff + mypy
make format      # auto-fix lint issues
make clean       # remove venv, node_modules, DB
```

Or directly:

```bash
pytest
pytest --cov=labelforge --cov-report=term-missing
ruff check labelforge tests backend
mypy labelforge backend
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `LABELFORGE_DB_PATH` | `backend/labelforge.db` | Path to the SQLite database file |
