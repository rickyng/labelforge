"""Tests for POST /api/import-json/{session_id}."""
from fastapi.testclient import TestClient


def test_import_json_route_exists():
    """Endpoint returns 404 for unknown session (not 405 — route must exist)."""
    from backend.main import app
    client = TestClient(app)
    resp = client.post(
        "/api/import-json/nonexistent-session",
        files={"file": ("order.json", b'{"Styles":[]}', "application/json")},
        cookies={"role": "admin"},
    )
    assert resp.status_code != 405, "Route does not exist"
