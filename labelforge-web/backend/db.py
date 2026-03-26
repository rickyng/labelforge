"""SQLite persistence for editable configs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).parent / "labelforge.db"


def init_db() -> None:
    """Create tables and run migrations if needed."""
    with _conn() as conn:
        # Check if the table exists at all
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='editable_configs'"
        ).fetchone()

        if not exists:
            # Fresh install — create with new schema
            conn.execute("""
                CREATE TABLE editable_configs (
                    name              TEXT PRIMARY KEY,
                    filename          TEXT NOT NULL DEFAULT '',
                    labels_json       TEXT NOT NULL,
                    editable_ids_json TEXT NOT NULL,
                    file_blob         BLOB,
                    file_type         TEXT NOT NULL DEFAULT 'pdf',
                    page_count        INTEGER NOT NULL DEFAULT 1,
                    updated_at        TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_labels (
                    name          TEXT PRIMARY KEY,
                    profile_name  TEXT NOT NULL,
                    fills_json    TEXT NOT NULL DEFAULT '{}',
                    updated_at    TEXT NOT NULL
                )
            """)
            return

        # Table exists — detect old schema (filename was PK)
        cols = {row[1]: row for row in conn.execute("PRAGMA table_info(editable_configs)").fetchall()}
        # In old schema, filename is column 0 (first/PK); in new schema, name is column 0
        old_schema = cols.get("filename") and cols["filename"][5] == 1  # cid==pk flag

        if old_schema:
            # Migrate: name becomes PK, filename becomes regular column
            conn.execute("""
                CREATE TABLE editable_configs_new (
                    name              TEXT PRIMARY KEY,
                    filename          TEXT NOT NULL DEFAULT '',
                    labels_json       TEXT NOT NULL,
                    editable_ids_json TEXT NOT NULL,
                    file_blob         BLOB,
                    file_type         TEXT NOT NULL DEFAULT 'pdf',
                    page_count        INTEGER NOT NULL DEFAULT 1,
                    updated_at        TEXT NOT NULL
                )
            """)
            conn.execute("""
                INSERT INTO editable_configs_new
                    (name, filename, labels_json, editable_ids_json, file_blob, file_type, page_count, updated_at)
                SELECT
                    COALESCE(NULLIF(name, ''), filename),
                    filename,
                    labels_json,
                    editable_ids_json,
                    file_blob,
                    file_type,
                    page_count,
                    updated_at
                FROM editable_configs
            """)
            conn.execute("DROP TABLE editable_configs")
            conn.execute("ALTER TABLE editable_configs_new RENAME TO editable_configs")
            return

        # New schema — add any missing columns for safety
        if "filename" not in cols:
            conn.execute("ALTER TABLE editable_configs ADD COLUMN filename TEXT NOT NULL DEFAULT ''")
        if "file_blob" not in cols:
            conn.execute("ALTER TABLE editable_configs ADD COLUMN file_blob BLOB")

        # Ensure user_labels table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_labels (
                name          TEXT PRIMARY KEY,
                profile_name  TEXT NOT NULL,
                fills_json    TEXT NOT NULL DEFAULT '{}',
                updated_at    TEXT NOT NULL
            )
        """)


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_config(
    name: str,
    filename: str,
    labels: list[dict],
    editable_ids: list[str],
    file_blob: bytes,
    page_count: int,
    file_type: str,
) -> None:
    """Insert or replace a config entry keyed by name."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO editable_configs
                (name, filename, labels_json, editable_ids_json, file_blob, page_count, file_type, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                filename          = excluded.filename,
                labels_json       = excluded.labels_json,
                editable_ids_json = excluded.editable_ids_json,
                file_blob         = excluded.file_blob,
                page_count        = excluded.page_count,
                file_type         = excluded.file_type,
                updated_at        = excluded.updated_at
            """,
            (
                name,
                filename,
                json.dumps(labels),
                json.dumps(editable_ids),
                file_blob,
                page_count,
                file_type,
                now,
            ),
        )


def update_name(old_name: str, new_name: str) -> bool:
    """Rename a profile. Returns True if found."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE editable_configs SET name = ? WHERE name = ?",
            (new_name, old_name),
        )
        return cur.rowcount > 0


def delete_config(name: str) -> bool:
    """Delete a config entry by name. Returns True if a row was deleted."""
    with _conn() as conn:
        cur = conn.execute("DELETE FROM editable_configs WHERE name = ?", (name,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_configs() -> list[dict]:
    """Return summary rows (no blob/labels)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT name, filename, editable_ids_json, page_count, file_type, updated_at "
            "FROM editable_configs ORDER BY updated_at DESC"
        ).fetchall()
    return [
        {
            "name": r["name"],
            "filename": r["filename"] or r["name"],
            "editable_count": len(json.loads(r["editable_ids_json"])),
            "page_count": r["page_count"],
            "file_type": r["file_type"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def get_config(name: str) -> dict | None:
    """Return full config row by name, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM editable_configs WHERE name = ?", (name,)
        ).fetchone()
    if row is None:
        return None
    return {
        "name": row["name"],
        "filename": row["filename"] or row["name"],
        "labels": json.loads(row["labels_json"]),
        "editable_ids": json.loads(row["editable_ids_json"]),
        "file_blob": row["file_blob"],
        "page_count": row["page_count"],
        "file_type": row["file_type"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# User labels
# ---------------------------------------------------------------------------

def list_user_labels() -> list[dict]:
    """Return summary rows for all user labels."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT name, profile_name, updated_at FROM user_labels ORDER BY updated_at DESC"
        ).fetchall()
    return [{"name": r["name"], "profile_name": r["profile_name"], "updated_at": r["updated_at"]} for r in rows]


def get_user_label(name: str) -> dict | None:
    """Return a user label row or None."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM user_labels WHERE name = ?", (name,)).fetchone()
    if row is None:
        return None
    return {
        "name": row["name"],
        "profile_name": row["profile_name"],
        "fills": json.loads(row["fills_json"]),
        "updated_at": row["updated_at"],
    }


def save_user_label(name: str, profile_name: str, fills: dict) -> None:
    """Upsert a user label."""
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO user_labels (name, profile_name, fills_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                profile_name = excluded.profile_name,
                fills_json   = excluded.fills_json,
                updated_at   = excluded.updated_at
            """,
            (name, profile_name, json.dumps(fills), now),
        )


def delete_user_label(name: str) -> bool:
    """Delete a user label. Returns True if found."""
    with _conn() as conn:
        cur = conn.execute("DELETE FROM user_labels WHERE name = ?", (name,))
        return cur.rowcount > 0
