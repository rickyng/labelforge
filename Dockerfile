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

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache)
COPY pyproject.toml README.md ./
COPY labelforge/ ./labelforge/
COPY backend/ ./backend/
RUN pip install --no-cache-dir -e ".[web]"

# Copy built frontend assets from Stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Run as non-root user
RUN useradd -m -u 1000 appuser \
    && mkdir -p /data && chown appuser:appuser /data \
    && chown -R appuser:appuser /app
USER appuser

ENV LABELFORGE_DB_PATH=/data/labelforge.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
