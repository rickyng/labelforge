"""Shared session store and dependency injectors."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Cookie, HTTPException, status


@dataclass
class SessionData:
    session_id: str
    input_path: Path
    file_type: str  # "pdf" or "ai"
    tmp_dir: Path
    output_path: Path | None = None
    labels_json_path: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# In-memory session store: sid -> SessionData
SESSION_STORE: dict[str, SessionData] = {}

# Editable config store: filename -> list of editable label IDs
EDITABLE_CONFIG: dict[str, list[str]] = {}

# The most recently analyzed session (shared with User view)
CURRENT_SESSION_ID: str | None = None


def set_current_session(session_id: str) -> None:
    global CURRENT_SESSION_ID
    CURRENT_SESSION_ID = session_id


def create_session(input_path: Path, file_type: str, tmp_dir: Path) -> SessionData:
    sid = str(uuid.uuid4())
    session = SessionData(
        session_id=sid,
        input_path=input_path,
        file_type=file_type,
        tmp_dir=tmp_dir,
    )
    SESSION_STORE[sid] = session
    return session


def get_session(session_id: str) -> SessionData:
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or expired.",
        )
    return session


# Hardcoded credentials (MVP only)
_CREDENTIALS: dict[str, tuple[str, str]] = {
    "admin": ("admin123", "admin"),
    "user": ("user123", "user"),
}


def verify_credentials(username: str, password: str) -> str | None:
    """Return role string if valid, else None."""
    entry = _CREDENTIALS.get(username)
    if entry and entry[0] == password:
        return entry[1]
    return None


def require_role(
    role: str | None = Cookie(default=None),
) -> str:
    """FastAPI dependency: ensure a valid role cookie is present."""
    if role not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )
    return role
