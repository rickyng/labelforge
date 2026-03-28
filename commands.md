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

## Global Options

| Flag | Short | Description |
|------|-------|-------------|
| `--version` | `-V` | Print version and exit |
| `--help` | | Show help for any command |

---

## Commands

### `analyze`

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

### `apply`

Apply an edited labels JSON file to a PDF/AI and write the modified output.
Only labels where `new_text` differs from `original_text` are processed.

```bash
labelforge apply INPUT_PDF LABELS_JSON [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `output.pdf` | Destination PDF file |
| `--backup` | `-b` | off | Copy input to `<input>.bak` before writing |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--output-format FORMAT` | | `pdf` | Output format: `pdf` or `ai` |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge apply invoice.pdf labels.json -o invoice_edited.pdf --force
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
| `--page RANGE` | `-p` | all | Limit to page range, e.g. `0` or `0-3` |
| `--all` | `-a` | off | Replace all occurrences (default: first only) |
| `--force` | `-f` | off | Overwrite output if it already exists |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge replace invoice.pdf "John Doe" "Jane Smith" -o out.pdf --all
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
| `--output PATH` | `-o` | `<input>.pdf` | Destination PDF file |
| `--verbose` | `-v` | off | Enable debug logging |

**Example:**
```bash
labelforge convert artwork.ai -o artwork.pdf
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

### `components`

Extract all component types (text, images, barcodes, shapes) from a PDF or `.ai` file into a JSON file.
Unlike `analyze` (text-only), this command includes images and barcodes. Barcode values are decoded automatically if `libzbar` is installed.

```bash
labelforge components INPUT_FILE [options]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output PATH` | `-o` | `components.json` | Destination JSON file |
| `--types LIST` | `-t` | all | Comma-separated types to include: `TEXT,IMAGE,BARCODE,SHAPE` |
| `--pretty / --compact` | | `--pretty` | Pretty-print or compact JSON |
| `--verbose` | `-v` | off | Enable debug logging |

**Prerequisites for barcode detection:**
- macOS: `brew install zbar`
- Linux/Docker: `apt install libzbar0`

**Example:**
```bash
# Extract everything
labelforge components artwork.ai -o components.json

# Extract barcodes only
labelforge components artwork.ai --types BARCODE -o barcodes.json
```

---

## Typical Workflow

```bash
# 1. Extract labels from a PDF
labelforge analyze invoice.pdf -o labels.json

# 2. Edit labels.json — set new_text on the spans you want to change

# 3. Preview what will change
labelforge inspect labels.json --changed-only

# 4. Apply changes
labelforge apply invoice.pdf labels.json -o invoice_out.pdf
```
