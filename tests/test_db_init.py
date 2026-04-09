import importlib
import sqlite3


def test_init_creates_tables(tmp_path, monkeypatch):
    """init_db() must create both tables on a fresh file."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("LABELFORGE_DB_PATH", str(db_file))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    conn = sqlite3.connect(str(db_file))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "editable_configs" in tables
    assert "user_labels" in tables


def test_init_is_idempotent(tmp_path, monkeypatch):
    """Calling init_db() twice must not raise."""
    db_file = tmp_path / "test2.db"
    monkeypatch.setenv("LABELFORGE_DB_PATH", str(db_file))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    db_mod.init_db()


def test_editable_configs_columns(tmp_path, monkeypatch):
    """editable_configs must have all required columns."""
    db_file = tmp_path / "test3.db"
    monkeypatch.setenv("LABELFORGE_DB_PATH", str(db_file))
    import backend.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    conn = sqlite3.connect(str(db_file))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(editable_configs)").fetchall()}
    conn.close()
    expected = {
        "name", "filename", "labels_json", "editable_ids_json",
        "file_blob", "file_type", "page_count", "input_json",
        "changes_json", "updated_at",
    }
    assert expected <= cols
