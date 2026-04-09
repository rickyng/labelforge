# LabelForge — End-to-End Workflow

> LabelForge is a PDF/AI label editor with a single-page interface: upload order data, select a template, preview and apply changes, then download the output PDF.

---

## 1. Workflow Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Upload Order │───▶│ Select Label │───▶│ Preview &    │───▶│ Download     │
│ JSON         │    │ Template     │    │ Apply        │    │ Output PDF   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

No login or auth required. Single Editor page at `/`.

---

## 2. Step-by-Step

### Step 1 — Upload Order JSON

- Upload an **order JSON file** via drag-and-drop (`UploadZone` component).
- `POST /api/upload` validates JSON format, stores it in a server-side temp session, returns a `session_id`.

### Step 2 — Select a Label Template

- Pick a **label template** from a dropdown (e.g. ADHEDIST, GI, PV — Mango variants).
- `GET /api/templates` lists available templates and their field counts.
- On selection, the system:
  1. Loads the **AI file** associated with the template.
     - `POST /api/templates/{name}/load-ai` — runs PyMuPDF analysis, returns `Label[]` + `page_count`.
  2. **Maps template fields** against the uploaded order JSON.
     - `POST /api/templates/{name}/map` — resolves order data to component IDs, returns per-size changes.

- The left panel displays:
  - **Field Mapping table** — PDF field, JSON path, value per size (resizable columns).
  - **Intended Values table** — component ID ↔ deduced value from mapping.
  - **Component table** — all components (TEXT, SHAPE, IMAGE, BARCODE) with type filter and hover sync.
- The PDF preview renders with a **bbox overlay** showing component positions.

### Step 3 — Navigate Sizes & Preview

- Navigate **size variants** (e.g. S, M, L, XL) using prev/next controls.
- Switching sizes auto-re-applies if in edited mode; zoom, overlay, and view mode are preserved.
- Toggle **Original / Edited** view:
  - Original: AI template rasterized preview with overlay boxes.
  - Edited: `POST /api/templates/{name}/apply-direct` runs `apply_from_components()` (redact-then-insert), then rasterized output preview.
- Both views use the same rendering path (rasterized PNG at consistent DPI) for identical sizing.

### Step 4 — Download

- Click **Download** to get the output PDF.
- `GET /api/download/{session_id}` streams the output file.

---

## 3. Data Flow

```
                          ┌──────────────────────────────────────────────┐
                          │               In-Memory Session Store        │
                          │                                              │
                          │  SESSION_STORE[session_id]:                  │
                          │    - input_path (AI/PDF)                     │
                          │    - output_path (edited PDF)                │
                          │    - preview_images (rasterized PNGs)        │
                          │    - extra["changes_data"] (mapping results) │
                          │    - extra["components"]                     │
                          └───────────┬──────────────────────▲───────────┘
                                      │                      │
          ┌───────────────────────────┼──────────────────────┼───────────────┐
          │                           │                      │               │
          ▼                           ▼                      │               ▼
   ┌──────────────┐          ┌──────────────┐        ┌──────────────┐  ┌──────────────┐
   │  Editor.tsx  │          │  API Layer   │        │  Apply       │  │  Apply Utils │
   │              │          │  (FastAPI)   │        │  Engine      │  │              │
   │ - Upload     │─POST───▶│              │─store─▶│ (PyMuPDF)    │  │ shape → text │
   │ - Template   │─POST───▶│ /upload      │        │              │◀─│ → barcode    │
   │ - Map        │─POST───▶│ /templates/* │        │ redact +     │  │ overlap text │
   │ - Apply      │─POST───▶│ /apply-direct│        │ insert text  │  │ re-insertion │
   │ - Download   │─GET────▶│ /download/*  │        │              │  │              │
   └──────────────┘          └──────────────┘        └──────────────┘  └──────────────┘
```

---

## 4. Apply Pipeline

The apply pipeline processes changes in a specific order to preserve content:

1. **Shape fill changes** (redact shape area → redraw with new fill)
2. **Text changes** (redact original text → insert new text with full font resolution)
   - Text overlapping with shapes is automatically re-inserted with the same font pipeline
   - Font resolution: embedded font → system font file → built-in fallback
3. **Barcode replacement** (generate barcode image → replace in PDF)
4. **Barcode regions** (vector-drawn barcodes via mapping config)

---

## 5. Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload order JSON file, create session |
| GET | `/api/templates` | List available label templates |
| GET | `/api/templates/{name}` | Get template field definitions |
| POST | `/api/templates/{name}/load-ai` | Load AI file, extract components |
| POST | `/api/templates/{name}/map` | Map order JSON to component IDs per size |
| POST | `/api/templates/{name}/apply-direct` | Apply changes, generate output PDF |
| POST | `/api/components/{sid}` | Extract components (TEXT, IMAGE, BARCODE, SHAPE) |
| GET | `/api/preview/{sid}` | Stream original PDF for preview |
| GET | `/api/preview-images/{sid}` | Rasterized PNG preview images |
| GET | `/api/output-preview/{sid}` | Stream output PDF for preview |
| GET | `/api/download/{sid}` | Download the output PDF |

---

## 6. Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript, Vite 5, Tailwind CSS 3 |
| PDF Rendering | PDF.js (canvas) + rasterized PNG preview (ImageViewer) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| PDF Engine | PyMuPDF (`fitz`) — text extraction + redact-then-insert editing |
| Database | Turso (libsql) for production |
| Validation | Pydantic v2 (all API boundaries) |
| State | React Context (`LabelsContext`) + in-memory session store |

---

## 7. Label Template System

Templates bridge **order data** and **PDF labels**:

```
Order JSON ──▶ Template Fields ──▶ Mapping (build_changes) ──▶ Component IDs ──▶ Apply
   (data)       (field defs)         (per-template logic)        (PDF spans)      (output)
```

- Each template defines **fields** with JSON paths to extract from order data.
- A **mapping registry** (`labelforge/mappings/`) auto-detects the template type and provides:
  - `build_changes()` — maps resolved fields to component_id → value per size
  - Custom formatting (prefixes, value transforms, field combinations)
- Per-template formatting:
  - **GI**: Color code before `:`, `C:` prefix; REF with 4-digit spacing
  - **PV**: REF with `REF:` prefix + 4-digit spacing; Size Range `/` → space; ORIGIN uppercase with `MADE IN` prefix; Price split on comma

---

## 8. Mappings

| Mapping | Template | Key Formatting |
|---------|----------|---------------|
| `mango_adhedist` | ADHEDIST-mango | Standard field assignment |
| `mango_gi` | GI001BAW-GI001BAC | Color code only (`:` split), `C:` prefix, shape fill → blue |
| `mango_pv` | PVPV0102-PVP002XG | REF prefix + spacing, Size Range `/` → space, ORIGIN uppercase, price split, barcode regions |
