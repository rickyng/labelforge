# CLAUDE.md — LabelForge

This file gives Claude context about the project structure, conventions, and workflow.

---

## Project Overview

LabelForge is a PDF/AI text-label editor. It extracts text spans from a PDF, lets users edit the text, and re-applies changes using a redact-then-insert strategy (PyMuPDF). Adobe Illustrator `.ai` files are supported via their embedded PDF layer.

Two roles:
- **Admin** — uploads PDFs, marks spans as editable, saves named profiles
- **User** — fills in replacement text for editable fields, downloads the output PDF

---

## Tech Stack

### Backend
- Python 3.11+, FastAPI, Uvicorn
- PyMuPDF (`fitz`) for PDF extraction and editing
- SQLite (raw SQL, no ORM) via `backend/db.py`
- Pydantic v2 for schemas
- In-memory session store (`SESSION_STORE` dict in `backend/dependencies.py`)
- Auth: hardcoded credentials + HTTP-only `role` cookie

### Frontend
- React 18 + TypeScript, Vite 5
- React Router v6
- Tailwind CSS v3
- PDF.js (`pdfjs-dist`) — renders PDF pages onto `<canvas>`, worker loaded from CDN
- Konva / react-konva — interactive bbox overlays on the PDF canvas
- Native `fetch` (no Axios)
- React Context for global label state (`LabelsContext`)

---

## Directory Structure

```
labelforge/
├── backend/
│   ├── main.py              # FastAPI app, CORS, static files, lifespan
│   ├── db.py                # SQLite init, migrations, queries
│   ├── dependencies.py      # Auth, session store, require_role
│   ├── schemas.py           # Pydantic request/response models
│   ├── utils.py             # Temp session directory helpers only
│   └── routers/
│       ├── upload.py        # POST /api/upload
│       ├── analyze.py       # POST /api/analyze
│       ├── apply.py         # POST /api/apply
│       ├── download.py      # GET  /api/download/{sid}
│       ├── configs.py       # CRUD /api/configs (named profiles)
│       ├── editable.py      # POST /api/editable/{sid} — persist profile (derives labels from components)
│       └── user_labels.py   # CRUD /api/user-labels
├── frontend/
│   ├── src/
│   │   ├── api.ts           # All fetch calls to the backend
│   │   ├── types.ts         # Label and other shared TypeScript types
│   │   ├── context/
│   │   │   └── LabelsContext.tsx  # Global label state, selected/hovered IDs
│   │   ├── components/
│   │   │   ├── PdfViewer.tsx      # PDF.js canvas renderer, accepts zoom + overlay
│   │   │   ├── AdminOverlay.tsx   # Konva bbox overlay for label display
│   │   │   ├── ZoomControls.tsx   # Reusable zoom +/- /reset buttons
│   │   │   ├── LabelTable.tsx     # Sidebar label list with type filter (TEXT/SHAPE/IMAGE/BARCODE)
│   │   │   ├── UserForm.tsx       # Editable fields form (User)
│   │   │   ├── UploadZone.tsx     # Drag-and-drop file upload
│   │   │   ├── Toast.tsx          # Toast notification system
│   │   │   └── TagIcon.tsx        # Logo SVG
│   │   ├── pages/
│   │   │   ├── Admin.tsx          # Admin editor page
│   │   │   ├── User.tsx           # User text-fill page
│   │   │   └── Login.tsx          # Login page
│   │   └── utils/
│   │       └── auth.ts            # getRole() reads role cookie
│   ├── package.json
│   ├── vite.config.ts       # Proxies /api/* to localhost:8000
│   └── tailwind.config.js
├── labelforge/              # Core Python library (CLI + PDF engine)
│   ├── cli.py               # Typer CLI: components, apply, analyze, replace, build, convert, inspect
│   ├── applier.py           # redact-then-insert engine; apply_labels, apply_from_components
│   ├── analyzer.py          # Text-span extraction (legacy analyze command)
│   ├── document_analyzer.py # Multi-type component extraction (TEXT, IMAGE, BARCODE, SHAPE)
│   ├── component_models.py  # Pydantic models: ComponentsFile, DocumentComponent
│   ├── models.py            # Core Label Pydantic model
│   ├── utils.py             # Font resolution, color helpers, extract_embedded_fonts
│   ├── barcode_handler.py   # Barcode decode/overlay via libzbar
│   ├── shape_handler.py     # Shape fill color modification (redact-then-redraw)
│   ├── changes_generator.py # CSV parsing, column role classification, changes building
│   ├── mappings/            # Auto-discovered mapping registry (one file per template)
│   │   ├── __init__.py          # pkgutil auto-discovery → MAPPINGS, MAPPING_FINGERPRINTS, get_assign_fn()
│   │   ├── mango_adhedist.py    # ADHEDIST field map, fingerprint, assign function
│   │   ├── mango_gi.py          # GI field map, fingerprint, assign function
│   │   └── mango_pv.py          # PV (price tag) field map, fingerprint, assign function
│   ├── ADHEDIST-mango-json_to_csv.py  # External order JSON → ADHEDIST CSV
│   ├── GI-mango-json_to_csv.py        # External order JSON → GI CSV
│   └── PV-mango-json_to_csv.py        # External order JSON → PV CSV
├── generate_changes.py      # Script: Mango order JSON + components.json → per-size changes.json
├── start.sh                 # Dev launcher (macOS/Linux)
├── start.ps1                # Dev launcher (Windows)
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md
```

---

## Running the Project

### Backend
```bash
# From project root
uvicorn backend.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
# /api/* requests are proxied to http://localhost:8000
```

### Both at once (macOS/Linux)
```bash
./start.sh
```

### Both at once (Windows)
```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
Requires `.venv` created at project root and `npm` on PATH.

### Docker (full stack)
```bash
docker-compose up --build
```

---

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/login` | Sets `role` + `username` cookies |
| POST | `/api/logout` | Clears cookies |
| POST | `/api/upload` | Upload PDF/AI file, returns `session_id` |
| POST | `/api/analyze` | Extract labels from uploaded file |
| GET | `/api/preview/{sid}` | Stream PDF for rendering |
| POST | `/api/apply/{sid}` | Apply text edits, produce output |
| GET | `/api/download/{sid}` | Download edited PDF |
| GET/POST/DELETE | `/api/configs` | Named profile CRUD |
| GET/POST | `/api/editable/{sid}` | Get/set editable label IDs |
| GET/POST/DELETE | `/api/user-labels` | User text-fill set CRUD |

---

## Auth

Hardcoded credentials (MVP only — replace for production):
- `admin / admin123` → role `admin`
- `user / user123` → role `user`

Cookies: HTTP-only, SameSite=lax, max_age=86400. Frontend reads the `role` cookie via `getRole()` in `utils/auth.ts` to guard routes on mount.

---

## Data Flow

```
Upload PDF
  → POST /api/upload        (stores file in /tmp/labelforge/<uuid>/)
  → POST /api/analyze       (PyMuPDF extracts text spans → Label[])
  → labels stored in SESSION_STORE[session_id]

Admin marks editables
  → POST /api/editable      (list of label IDs)
  → POST /api/configs       (saves profile: labels + editable IDs + file blob to SQLite)

Admin imports CSV (optional — pre-fill from order data)
  → POST /api/import-csv    (parses 1-header-row CSV, uses mapping to build {component_id: value})
  → mapping detected via fingerprint on extracted components
  → returns changes_by_size + fields_by_size to frontend

User fills form
  → POST /api/user-labels   (saves {label_id → new_text} map to SQLite)
  → POST /api/apply         (PyMuPDF redact-then-insert → output file)
  → GET  /api/download      (streams output)
```

### CSV Import Pipeline

The converter scripts (`ADHEDIST-mango-json_to_csv.py`, etc.) transform external order JSON/Excel into unified 1-header-row CSVs. The import pipeline only handles this format:

```
External order data (JSON/Excel)
  → *-json_to_csv.py converter → 1-header-row CSV (e.g. AD.csv, GI.csv, PV.csv)
  → POST /api/import-csv      → classify_column() maps headers to semantic roles
  → mapping-specific assign() → {component_id: new_value}
```

Each mapping file in `labelforge/mappings/` defines:
- `FIELD_MAP` — semantic role → component ID
- `FINGERPRINT` — unique component IDs for auto-detection
- `assign(row_values, assign_fn)` — template-specific field formatting (Pipeline 1: CSV)
- `build_changes(resolved_fields)` — maps resolved fields to component_id → value (Pipeline 2: JSON order)

---

## PDF Rendering (Frontend)

- `PdfViewer` renders each page onto `<canvas>` using PDF.js
- Scale = `(containerWidth / pdfWidth) * zoom`
- `onDimensions(w, h, scale)` fires after each render so overlays can align
- Overlay (`AdminOverlay`) is a Konva `<Stage>` absolutely positioned on top of the canvas
- Label bbox coords are in PDF point space; multiply by `pdfScale` to get canvas pixels
- Each page panel is `h-screen` with `flex-1 overflow-auto` scroll on the PDF area only

---

## Key Conventions

- **No ORM** — raw SQL in `db.py`; schema migrations via `ALTER TABLE` in `init_db()`
- **No Axios** — all API calls use native `fetch` in `api.ts`
- **No Redux** — global state is React Context (`LabelsContext`)
- **Mappings auto-discovered** — drop a file in `labelforge/mappings/` with `MAPPING_NAME`, `FIELD_MAP`, `FINGERPRINT`, `assign()` and it's registered automatically
- **CSV import = 1 header row** — converter scripts produce unified CSVs; the import pipeline only handles 1-header-row format
- **Component ID format**: `p{page}_t_b{block}_l{line}_s{span}` for TEXT; `p{page}_shape_{idx}` for SHAPE; `p{page}_img_{idx}` for IMAGE; `p{page}_barcode_{idx}` for BARCODE
- **Apply order**: shapes applied BEFORE text — redaction removes overlapping content, so shapes must be redrawn before text insertion
- **Same-file saves**: PyMuPDF requires `save()` to a temp file then rename when input == output — both `apply_labels` and `apply_shape_fill_change` handle this
- **Shared UI components** go in `frontend/src/components/`; page-specific logic stays in `pages/`
- **Zoom controls** are a shared `ZoomControls` component — don't duplicate inline
- **`min-h-screen` → `h-screen overflow-hidden`** on page roots to keep scrolling inside panels
- TypeScript strict mode; Pydantic v2 models for all API boundaries
- Tailwind utility classes only — no custom CSS files
- Toast notifications via `useToast()` hook from `Toast.tsx`

---

## Environment / Secrets

No `.env` file required for development. For production:
- Replace hardcoded credentials in `backend/dependencies.py`
- Set a real secret for cookie signing
- Move SQLite path out of the repo if persisting data

---

## Common Tasks

### Add a new mapping
1. Create `labelforge/mappings/your_mapping.py` with four exports: `MAPPING_NAME` (str), `FIELD_MAP` (dict), `FINGERPRINT` (set), `assign(row_values, assign_fn)` (function)
2. Auto-discovery in `labelforge/mappings/__init__.py` picks it up on import — no other registration needed
3. Create a converter script (e.g. `labelforge/YOUR_MAPPING-json_to_csv.py`) to transform external order data into 1-header-row CSV
4. Update `changes_generator.py` if new column roles are needed in `classify_column` / `extract_row_values`

### Add a new API endpoint
1. Create a router in `backend/routers/your_router.py`
2. Register it in `backend/main.py` with `app.include_router(...)`
3. Add the fetch call to `frontend/src/api.ts`
4. Add response types to `frontend/src/types.ts` if needed

### Add a new label field
1. Add the field to the `Label` interface in `frontend/src/types.ts`
2. Update the Pydantic model in `backend/schemas.py`
3. Update the core `Label` model in `labelforge/models.py`
4. Update extraction logic in `labelforge/analyzer.py` (text spans) and/or `labelforge/document_analyzer.py` (components)
5. Update `AdminOverlay.tsx` and/or `LabelTable.tsx` to display it

### Add a new page
1. Create `frontend/src/pages/YourPage.tsx`
2. Add a route in `frontend/src/main.tsx` (or wherever the router is defined)
3. Guard with `getRole()` check on mount if auth-protected
