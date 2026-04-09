"""SQLite / Turso persistence for editable configs."""
from __future__ import annotations

import json,os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import libsql


def _rows_as_dicts(cursor) -> list[dict]:
    """Convert all cursor results to list of dicts."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _row_as_dict(cursor) -> dict | None:
    """Convert single cursor result to dict, or None."""
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


# Turso cloud DB (Render / production) — fall back to local SQLite (dev)
TURSO_URL = os.environ.get("TURSO_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
DB_PATH = Path(os.environ.get("LABELFORGE_DB_PATH", str(Path(__file__).parent / "labelforge.db")))


def init_db()->None:
    """Create tables if they do not already exist. Runs lightweight migrations."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS editable_configs (
                name              TEXT PRIMARY KEY,
                filename          TEXT NOT NULL DEFAULT '',
                labels_json       TEXT NOT NULL DEFAULT '[]',
                editable_ids_json TEXT NOT NULL DEFAULT '[]',
                file_blob         BLOB,
                file_type         TEXT NOT NULL DEFAULT 'pdf',
                page_count        INTEGER NOT NULL DEFAULT 1,
                input_json        TEXT,
                changes_json      TEXT NOT NULL DEFAULT '{}',
                mapping_name      TEXT,
                updated_at        TEXT NOT NULL
            )
        """)
        # Migration: add mapping_name if upgrading from older schema
        existing = {row[1] for row in conn.execute("PRAGMA table_info(editable_configs)").fetchall()}
        if "mapping_name" not in existing:
            conn.execute("ALTER TABLE editable_configs ADD COLUMN mapping_name TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_labels (
                name          TEXT PRIMARY KEY,
                profile_name  TEXT NOT NULL,
                fills_json    TEXT NOT NULL DEFAULT '{}',
                updated_at    TEXT NOT NULL
            )
        """)


@contextmanager
def _conn()->Generator:
    if TURSO_URL:
        # Turso embedded replica: local file synced with remote
        conn = libsql.connect(database=str(DB_PATH), sync_url=TURSO_URL, auth_token=TURSO_AUTH_TOKEN)
        conn.sync()
    else:
        conn = libsql.connect(database=str(DB_PATH))
    try:
        yield conn
        conn.commit()
        if TURSO_URL:
            conn.sync()
    finally:
        conn.close()


# editable_configs -- write

def save_config(
    name:str,
    filename:str,
    labels:list[dict],
    editable_ids:list[str],
    file_blob:bytes,
    page_count:int,
    file_type:str,
    input_json:str|None=None,
    changes_json:str|None=None,
    mapping_name:str|None=None,
)->None:
    """Upsert a named editable config."""
    now=datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO editable_configs
                (name,filename,labels_json,editable_ids_json,file_blob,
                 page_count,file_type,input_json,changes_json,mapping_name,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                filename=excluded.filename,
                labels_json=excluded.labels_json,
                editable_ids_json=excluded.editable_ids_json,
                file_blob=excluded.file_blob,
                page_count=excluded.page_count,
                file_type=excluded.file_type,
                input_json=excluded.input_json,
                changes_json=excluded.changes_json,
                mapping_name=excluded.mapping_name,
                updated_at=excluded.updated_at
            """,
            (
                name,filename,
                json.dumps(labels),
                json.dumps(editable_ids),
                file_blob,page_count,file_type,
                input_json,
                changes_json if changes_json is not None else """{}""",
                mapping_name,
                now,
            ),
        )


# editable_configs -- read

def list_configs()->list[dict]:
    """Return summary rows for all configs."""
    with _conn() as conn:
        cur = conn.execute(
            """
            SELECT name, filename, file_type, page_count, updated_at,
                   json_array_length(editable_ids_json) AS editable_count,
                   CASE WHEN changes_json IS NOT NULL AND changes_json != '{}'
                        THEN 1 ELSE 0 END AS has_changes
            FROM editable_configs
            ORDER BY updated_at DESC
            """
        )
        rows = _rows_as_dicts(cur)
        return [{**r, "has_changes": bool(r["has_changes"])} for r in rows]


def get_config(name:str)->dict|None:
    """Return a single config row with parsed JSON fields, or None."""
    with _conn() as conn:
        cur = conn.execute(
            """SELECT * FROM editable_configs WHERE name=?""",
            (name,),
        )
        row = _row_as_dict(cur)
    if row is None:
        return None
    row["labels"] = json.loads(row.pop("labels_json"))
    row["editable_ids"] = json.loads(row.pop("editable_ids_json"))
    return row


def update_name(old:str,new:str)->bool:
    """Rename a config. Returns True if found."""
    with _conn() as conn:
        cur=conn.execute(
            """UPDATE editable_configs SET name=? WHERE name=?""",
            (new,old),
        )
        return cur.rowcount>0


def delete_config(name:str)->bool:
    """Delete a config. Returns True if found."""
    with _conn() as conn:
        cur=conn.execute(
            """DELETE FROM editable_configs WHERE name=?""",
            (name,),
        )
        return cur.rowcount>0


# user_labels -- write

def save_user_label(name:str,profile_name:str,fills:dict)->None:
    """Upsert a user label set."""
    now=datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO user_labels (name,profile_name,fills_json,updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                profile_name=excluded.profile_name,
                fills_json=excluded.fills_json,
                updated_at=excluded.updated_at
            """,
            (name,profile_name,json.dumps(fills),now),
        )


# user_labels -- read

def list_user_labels()->list[dict]:
    """Return summary rows for all user labels."""
    with _conn() as conn:
        cur = conn.execute(
            """SELECT name,profile_name,updated_at FROM user_labels ORDER BY updated_at DESC"""
        )
        return _rows_as_dicts(cur)


def get_user_label(name:str)->dict|None:
    """Return a single user label row with parsed fills, or None."""
    with _conn() as conn:
        cur = conn.execute(
            """SELECT * FROM user_labels WHERE name=?""",
            (name,),
        )
        row = _row_as_dict(cur)
    if row is None:
        return None
    row["fills"] = json.loads(row.pop("fills_json"))
    return row


def delete_user_label(name:str)->bool:
    """Delete a user label. Returns True if found."""
    with _conn() as conn:
        cur=conn.execute(
            """DELETE FROM user_labels WHERE name=?""",
            (name,),
        )
        return cur.rowcount>0
