#!/usr/bin/env bash
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; RESET="\033[0m"
info()  { echo -e "${GREEN}[setup]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[setup]${RESET} $*"; }
error() { echo -e "${RED}[setup]${RESET} $*" >&2; exit 1; }

# ── Checks ───────────────────────────────────────────────────────────────────
info "Checking prerequisites…"

# Python ≥ 3.11
PYTHON=$(command -v python3 || true)
[ -z "$PYTHON" ] && error "python3 not found. Install Python ≥ 3.11 from https://python.org"
PY_VER=$($PYTHON -c 'import sys; print(sys.version_info[:2])')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info[0])')
PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info[1])')
[ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]) \
  && error "Python ≥ 3.11 required (found $(python3 --version)). Please upgrade."
info "  Python $(python3 --version) ✓"

# Node ≥ 18
NODE=$(command -v node || true)
[ -z "$NODE" ] && error "node not found. Install Node.js ≥ 18 from https://nodejs.org"
NODE_MAJOR=$(node -e 'process.stdout.write(String(process.versions.node.split(".")[0]))')
[ "$NODE_MAJOR" -lt 18 ] && error "Node.js ≥ 18 required (found $(node --version)). Please upgrade."
info "  Node.js $(node --version) ✓"

# npm
command -v npm >/dev/null 2>&1 || error "npm not found. It should ship with Node.js."
info "  npm $(npm --version) ✓"

# ── Python venv ───────────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  info "Creating Python virtual environment…"
  python3 -m venv .venv
else
  info "Virtual environment already exists, skipping creation."
fi

info "Installing Python dependencies (this may take a moment)…"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[web,dev]"
info "  Python deps installed ✓"

# ── Frontend ──────────────────────────────────────────────────────────────────
info "Installing frontend dependencies…"
(cd frontend && npm install --silent)
info "  Frontend deps installed ✓"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  LabelForge setup complete!${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  Next step:  make dev"
echo ""
echo "  URLs"
echo "    Frontend  →  http://localhost:5173"
echo "    API docs  →  http://localhost:8000/docs"
echo "    Health    →  http://localhost:8000/api/health"
echo ""
echo "  Credentials"
echo "    admin / admin123  (full editor)"
echo "    user  / user123   (text-only)"
echo ""
