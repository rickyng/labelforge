# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python deps first (layer cache)
COPY pyproject.toml ./
COPY labelforge/ ./labelforge/
RUN pip install --no-cache-dir -e ".[web]"

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend assets from Stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Data directory for the SQLite DB (override with LABELFORGE_DB_PATH)
RUN mkdir -p /data
ENV LABELFORGE_DB_PATH=/data/labelforge.db

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
