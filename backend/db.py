"""SQLite persistence for editable configs."""
from __future__ import annotations

import json,os,sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

DB_PATH=Path(os.environ.get("LABELFORGE_DB_PATH",str(Path(__file__).parent/"labelforge.db")))


def init_db()->None:
    """Create tables if they do not already exist. No migration logic."""
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


@contextmanager
def _conn()->Generator[sqlite3.Connection,None,None]:
    conn=sqlite3.connect(str(DB_PATH))
    conn.row_factory=sqlite3.Row
    try:
        yield conn
        conn.commit()
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
)->None:
    """Upsert a named editable config."""
    now=datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO editable_configs
                (name,filename,labels_json,editable_ids_json,file_blob,
                 page_count,file_type,input_json,changes_json,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                filename=excluded.filename,
                labels_json=excluded.labels_json,
                editable_ids_json=excluded.editable_ids_json,
                file_blob=excluded.file_blob,
                page_count=excluded.page_count,
                file_type=excluded.file_type,
                input_json=excluded.input_json,
                changes_json=excluded.changes_json,
                updated_at=excluded.updated_at
            """,
            (
                name,filename,
                json.dumps(labels),
                json.dumps(editable_ids),
                file_blob,page_count,file_type,
                input_json,
                changes_json if changes_json is not None else """{}""",
                now,
            ),
        )


# editable_configs -- read

def list_configs()->list[dict]:
    """Return summary rows for all configs."""
    with _conn() as conn:
        rows=conn.execute(
            """
            SELECT name, filename, file_type, page_count, updated_at,
                   json_array_length(editable_ids_json) AS editable_count,
                   CASE WHEN changes_json IS NOT NULL AND changes_json != '{}'
                        THEN 1 ELSE 0 END AS has_changes
            FROM editable_configs
            ORDER BY updated_at DESC
            """
        ).fetchall()
        return [{**dict(r), "has_changes": bool(r["has_changes"])} for r in rows]


def get_config(name:str)->dict|None:
    """Return a single config row with parsed JSON fields, or None."""
    with _conn() as conn:
        row=conn.execute(
            """SELECT * FROM editable_configs WHERE name=?""",
            (name,),
        ).fetchone()
    if row is None:
        return None
    d=dict(row)
    d["labels"]=json.loads(d.pop("labels_json"))
    d["editable_ids"]=json.loads(d.pop("editable_ids_json"))
    return d


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
        rows=conn.execute(
            """SELECT name,profile_name,updated_at FROM user_labels ORDER BY updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_label(name:str)->dict|None:
    """Return a single user label row with parsed fills, or None."""
    with _conn() as conn:
        row=conn.execute(
            """SELECT * FROM user_labels WHERE name=?""",
            (name,),
        ).fetchone()
    if row is None:
        return None
    d=dict(row)
    d["fills"]=json.loads(d.pop("fills_json"))
    return d


def delete_user_label(name:str)->bool:
    """Delete a user label. Returns True if found."""
    with _conn() as conn:
        cur=conn.execute(
            """DELETE FROM user_labels WHERE name=?""",
            (name,),
        )
        return cur.rowcount>0
