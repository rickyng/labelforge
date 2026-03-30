"""LabelForge Web — FastAPI application entry point.

Run from labelforge-web/ root:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .dependencies import verify_credentials
from .db import init_db
from .routers import analyze, apply, configs, components, download, editable, upload, user_labels
from .routers.import_json import router as import_json_router
from .schemas import AuthRequest, AuthResponse
from .utils import cleanup_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("LabelForge Web starting up.")
    init_db()
    yield
    logger.info("LabelForge Web shutting down — cleaning temp files.")
    cleanup_all()


app = FastAPI(
    title="LabelForge Web",
    description="PDF text label editor — web interface.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(apply.router, prefix="/api", tags=["apply"])
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(editable.router, prefix="/api", tags=["editable"])
app.include_router(configs.router, prefix="/api", tags=["configs"])
app.include_router(user_labels.router, prefix="/api", tags=["user_labels"])
app.include_router(components.router, prefix="/api", tags=["components"])
app.include_router(import_json_router, prefix="/api", tags=["import_json"])


@app.post("/api/auth/login", response_model=AuthResponse)
def login(body: AuthRequest, response: Response) -> AuthResponse:
    """Validate credentials and set a role cookie."""
    role = verify_credentials(body.username, body.password)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    response.set_cookie(
        key="role",
        value=role,
        httponly=False,  # frontend needs to read it
        samesite="lax",
        max_age=86400,
    )
    response.set_cookie(
        key="username",
        value=body.username,
        httponly=False,
        samesite="lax",
        max_age=86400,
    )
    return AuthResponse(role=role, username=body.username)  # type: ignore[arg-type]


@app.post("/api/auth/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("role")
    response.delete_cookie("username")
    return {"detail": "Logged out."}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve built frontend (production / Docker). Skipped in dev (dist won't exist).
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve real dist files when they exist, otherwise return index.html (SPA routing)."""
        candidate = _DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
