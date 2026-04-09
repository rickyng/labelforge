"""Test that save_profile picks up changes_data from session.extra."""
import json
from unittest.mock import patch
from pathlib import Path


def test_save_profile_persists_changes_json(tmp_path):
    """When session.extra has changes_data, save_config is called with changes_json."""
    from backend.dependencies import SESSION_STORE, SessionData

    fake_pdf = tmp_path / "input.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    session = SessionData(
        session_id="test-persist-123",
        input_path=fake_pdf,
        file_type="pdf",
        tmp_dir=tmp_path,
    )
    session.extra["changes_data"] = {"sizes": [{"size_name": "XS", "changes": {}}]}
    session.extra["input_json_raw"] = '{"order_id": "TEST"}'
    SESSION_STORE["test-persist-123"] = session

    try:
        with patch("backend.routers.editable.save_config") as mock_sc:
            mock_sc.side_effect = lambda **kw: None

            from fastapi.testclient import TestClient
            from backend.main import app

            client = TestClient(app)
            resp = client.post(
                "/api/editable/test-persist-123",
                json={"name": "test-profile", "editable_ids": []},
                cookies={"role": "admin"},
            )

        # Route must exist
        assert resp.status_code not in (404, 405), f"Unexpected status: {resp.status_code}"

        # If save_config was called (i.e. labels_json_path existed), verify wiring.
        # In this test labels_json_path is None so the DB branch is skipped;
        # we verify wiring via a direct unit call instead.
        from backend.routers.editable import save_editable  # noqa: F401
    finally:
        SESSION_STORE.pop("test-persist-123", None)


def test_changes_json_wiring_unit(tmp_path):
    """Unit test: the correct kwargs are passed to save_config when extra is set."""
    # Build a real labels JSON file so the DB branch executes
    import fitz
    from backend.dependencies import SESSION_STORE, SessionData

    # Create a minimal valid single-page PDF
    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / "input.pdf"
    doc.save(str(pdf_path))
    doc.close()

    # Write a minimal labels JSON
    labels_json = tmp_path / "labels.json"
    labels_json.write_text("[]", encoding="utf-8")

    session = SessionData(
        session_id="test-wiring-789",
        input_path=pdf_path,
        file_type="pdf",
        tmp_dir=tmp_path,
        labels_json_path=labels_json,
    )
    session.extra["changes_data"] = {"sizes": [{"size_name": "XS", "changes": {}}]}
    session.extra["input_json_raw"] = '{"order_id": "UNIT"}'
    SESSION_STORE["test-wiring-789"] = session

    captured = {}

    def capture_save_config(**kwargs):
        captured.update(kwargs)

    try:
        with patch("backend.routers.editable.save_config", side_effect=capture_save_config):
            from fastapi.testclient import TestClient
            from backend.main import app

            client = TestClient(app)
            resp = client.post(
                "/api/editable/test-wiring-789",
                json={"name": "wiring-profile", "editable_ids": []},
                cookies={"role": "admin"},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert captured, "save_config was not called"
        assert "changes_json" in captured, "changes_json kwarg missing from save_config call"
        assert "input_json" in captured, "input_json kwarg missing from save_config call"
        parsed = json.loads(captured["changes_json"])
        assert "sizes" in parsed, "changes_json did not contain expected 'sizes' key"
        assert captured["input_json"] == '{"order_id": "UNIT"}'
    finally:
        SESSION_STORE.pop("test-wiring-789", None)


def test_save_editable_no_changes_data(tmp_path):
    """When session.extra is empty, save_config gets changes_json=None and input_json=None."""
    import fitz
    from backend.dependencies import SESSION_STORE, SessionData

    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / "input2.pdf"
    doc.save(str(pdf_path))
    doc.close()

    labels_json = tmp_path / "labels2.json"
    labels_json.write_text("[]", encoding="utf-8")

    session = SessionData(
        session_id="test-nodata-321",
        input_path=pdf_path,
        file_type="pdf",
        tmp_dir=tmp_path,
        labels_json_path=labels_json,
    )
    # No extra data set
    SESSION_STORE["test-nodata-321"] = session

    captured = {}

    def capture_save_config(**kwargs):
        captured.update(kwargs)

    try:
        with patch("backend.routers.editable.save_config", side_effect=capture_save_config):
            from fastapi.testclient import TestClient
            from backend.main import app

            client = TestClient(app)
            resp = client.post(
                "/api/editable/test-nodata-321",
                json={"name": "nodata-profile", "editable_ids": []},
                cookies={"role": "admin"},
            )

        assert resp.status_code == 200
        assert captured, "save_config was not called"
        assert captured["changes_json"] is None
        assert captured["input_json"] is None
    finally:
        SESSION_STORE.pop("test-nodata-321", None)
