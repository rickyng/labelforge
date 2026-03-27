"""Temp directory helpers and cleanup utilities."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

TMP_ROOT = Path(tempfile.gettempdir()) / "labelforge"


def make_session_dir() -> Path:
    """Create a fresh UUID-named temp directory under /tmp/labelforge/."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(dir=TMP_ROOT))
    return tmp_dir


def cleanup_session_dir(tmp_dir: Path) -> None:
    """Remove a session temp directory and all its contents."""
    try:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
            logger.info("Cleaned up session dir: %s", tmp_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to clean up %s: %s", tmp_dir, exc)


def cleanup_all() -> None:
    """Remove entire /tmp/labelforge/ tree on shutdown."""
    try:
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)
            logger.info("Cleaned up all session dirs under %s", TMP_ROOT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to clean up %s: %s", TMP_ROOT, exc)
