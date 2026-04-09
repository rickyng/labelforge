# Render Deployment Plan — LabelForge Pilot

## Context

Deploy LabelForge to Render for production pilot testing. Single Docker container (FastAPI serves API + React frontend via SPA fallback). SQLite persists configs and user labels on a Render Disk.

## Changes

### 1. Create `render.yaml` (new file)

Render Blueprint with Docker web service, 1 GB persistent disk, secret env vars, health check.

### 2. Modify `Dockerfile` — 3 changes

- **Line 35**: Add `chmod 777 /data` so non-root appuser can write to Render disk mount
- **Lines 44-45**: HEALTHCHECK uses `${PORT:-8000}` instead of hardcoded 8000
- **Line 47**: CMD switches to shell-form with `${PORT:-8000}` (Render auto-assigns PORT)

### 3. No backend code changes

CORS, credentials, DB path, health check, and SPA fallback already env-var-driven.

## Deployment Steps

1. Apply Dockerfile + render.yaml changes, commit and push to `main`
2. Generate secure credentials: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` (run 4x)
3. Render dashboard: New > Web Service > connect repo
4. Render detects `render.yaml`; fill in secret env vars
5. Update `LABELFORGE_CORS_ORIGINS` to actual `.onrender.com` URL
6. Deploy and verify

## Verification

| Check | Expected |
|-------|----------|
| `curl /api/health` | `{"status":"ok"}` |
| Open URL in browser | Login page renders |
| Login with credentials | Redirected to Admin/User page |
| Save config, redeploy, check | Config persists (disk works) |
| Navigate to `/admin` directly | SPA fallback loads (not 404) |
| Open `/docs` | Swagger UI renders |

## Notes

- **Starter plan** (512 MB, 0.5 vCPU) sufficient for pilot
- **Cold starts**: ~30-60s after 15 min inactivity (Starter spins down)
- **Sessions**: In-memory `SESSION_STORE` resets on restart (acceptable for pilot)
- **SQLite WAL**: Add `PRAGMA journal_mode=WAL;` to `db.py` if concurrent writes cause issues
