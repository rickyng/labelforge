# LabelForge Web

A full-stack web application that wraps the **LabelForge CLI** (PyMuPDF-based PDF text label editor) in a FastAPI backend and React frontend with two role-based interfaces.

## Architecture

```
FastAPI (port 8000)  ←→  labelforge/ Python package (unchanged CLI core)
        ↑
React + Vite (port 5173)
  /login  — authentication
  /admin  — full label editor: bbox dragging, font controls, color picker
  /user   — simple text-only replacement form
```

All PDF analysis and label application goes through the same `analyzer.analyze_file()` and `applier.apply_labels()` functions used by the CLI. No code is duplicated.

## Quick Start

### Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18
- `uv` (recommended) or `pip`

### 1. Backend

```bash
cd labelforge-web

# Install Python dependencies
uv sync
# or: pip install -r requirements.txt

# Start the FastAPI server
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Swagger docs: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd labelforge-web/frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

## Login Credentials

| Role  | Username | Password |
|-------|----------|----------|
| Admin | `admin`  | `admin123` |
| User  | `user`   | `user123`  |

## Interfaces

### Admin (`/admin`)

- Full PDF preview via PDF.js
- All extracted labels displayed with editable fields:
  - `new_text` replacement
  - Bounding box (`x0`, `y0`, `x1`, `y1`) — also draggable on the PDF canvas overlay (react-konva)
  - Font size and color picker
  - `auto_fit`, `white_out`, `max_scale_down`, `padding` toggles
- Output format selector: **PDF** or **.ai** (with warning)
- "Apply All Changes" → generates output → download button appears

### User (`/user`)

- Same PDF preview
- Simple form: one text input per label (text replacement only)
- No position, font, or overflow controls exposed
- "Generate Updated File" → PDF output only

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/login` | Login, sets `role` cookie |
| `POST` | `/api/auth/logout` | Clear cookies |
| `POST` | `/api/upload` | Upload `.pdf` or `.ai` file |
| `POST` | `/api/analyze/{sid}` | Extract labels from uploaded file |
| `POST` | `/api/apply/{sid}` | Apply label edits, produce output |
| `GET`  | `/api/preview/{sid}` | Stream input file for PDF.js |
| `GET`  | `/api/download/{sid}` | Download output file |
| `GET`  | `/api/health` | Health check |

## Session Model

Sessions are purely in-memory (UUID-keyed dict) + temp files under `/tmp/labelforge/{uuid}/`. No database. Sessions are cleaned up on server shutdown. Each browser tab gets its own session after upload.

## .ai File Limitations

> **Warning:** Adobe Illustrator (`.ai`) files are read via their embedded PDF compatibility layer. Edits are applied to the PDF layer only. When re-opened in Illustrator, AI-specific features (live text, layers, effects) may not be preserved.
>
> For best results: export your `.ai` to PDF first (`File > Save As > PDF`, uncheck "Preserve Illustrator Editing Capabilities") before editing.

The `.ai` output format has the same limitation: LabelForge saves a PDF-compatible `.ai` file, not a native Illustrator document.

## Overflow Fix

The applier uses PyMuPDF's `insert_htmlbox` with `scale_low` (mapped from `max_scale_down`) for automatic font shrinking, plus optional `white_out` (white fill rect over redacted area) and `padding` (inset the insertion rect). These are all configurable per-label in the Admin interface.

## Development Notes

- Backend: FastAPI + Uvicorn + Pydantic v2 + PyMuPDF
- Frontend: React 18 + Vite + TypeScript + TailwindCSS + PDF.js + react-konva
- The `labelforge/` package inside `labelforge-web/` is a copy of the CLI package — keep it in sync manually if the CLI evolves.
- The Vite dev server proxies `/api` requests to `localhost:8000` automatically.
