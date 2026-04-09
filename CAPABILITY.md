# LabelForge CLI vs Web UI Capabilities

Last updated: 2026-04-09

## CLI Commands for `.ai` files

| Command | What it does | Output |
|---------|--------------|--------|
| `components` | Extract all TEXT, IMAGE, BARCODE, SHAPE components | `components.json` |
| `apply` | Apply changes via `--components` + `--changes` | Modified `.pdf` or `.ai` |
| `build` | Build PDF from labels only (no source) | `.pdf` file |
| `inspect` | View labels JSON in terminal table | — |

## What can be modified

| Feature | CLI | Web UI |
|---------|-----|--------|
| **TEXT** value change | ✅ via `changes.json` | ✅ via template field mapping |
| **TEXT** font preservation | ✅ embedded + system fonts | ✅ same pipeline |
| **BARCODE** embedded image replacement | ✅ QR, EAN-13, EAN-8, Code128, Code39, UPC-A | ❌ |
| **BARCODE_REGIONS** vector barcode generation | ✅ via mapping config (e.g. PV EAN-13) | ❌ |
| **SHAPE** fill color | ✅ via `changes.json` | ❌ |
| **SHAPE** overlap text preservation | ✅ re-inserts overlapping text after shape redaction | ✅ same pipeline |
| **IMAGE** replacement | ❌ | ❌ |
| **SHAPE** geometry | ❌ | ❌ |
| Template-based workflow | ❌ | ✅ |
| Visual overlay preview | ❌ | ✅ (Original/Edited toggle) |
| Field mapping table (PDF field / JSON path / value) | ❌ | ✅ |
| Intended values table (component ID ↔ value) | ❌ | ✅ |
| Resizable panel & columns | ❌ | ✅ |
| Size variant navigation | ✅ via `size_index` | ✅ with preserved zoom/view state |

## Source files that affect capabilities

| Capability | Files |
|------------|-------|
| CLI commands | `labelforge/cli.py` |
| TEXT apply | `labelforge/applier.py` (`apply_labels`, `apply_from_components`, `_insert_htmlbox`) |
| BARCODE apply | `labelforge/barcode_handler.py`, `labelforge/applier.py` |
| BARCODE_REGIONS | `labelforge/mappings/*.py` (`BARCODE_REGIONS`), `labelforge/applier.py` |
| SHAPE fill color | `labelforge/shape_handler.py`, `labelforge/applier.py` |
| Shape overlap text re-insertion | `labelforge/applier.py` (overlap detection in `apply_from_components`) |
| Component extraction | `labelforge/document_analyzer.py`, `labelforge/component_models.py` |
| Mappings | `labelforge/mappings/mango_adhedist.py`, `mango_gi.py`, `mango_pv.py` |
| Editor page | `frontend/src/pages/Editor.tsx` |
| Field mapping table | `frontend/src/components/FieldMappingTable.tsx` |
| Intended values table | `frontend/src/components/IntendedValuesTable.tsx` |
| Overlay preview | `frontend/src/components/AdminOverlay.tsx` |
| Label table | `frontend/src/components/LabelTable.tsx` |
| PDF viewer | `frontend/src/components/PdfViewer.tsx` (ImageViewer + PDF.js dual path) |
| API endpoints | `backend/routers/*.py`, `frontend/src/api.ts` |
