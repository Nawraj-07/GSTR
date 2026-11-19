from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "gstr9c"


def test_validate_gstin_requires_auth():
    r = client.post("/api/v1/gst/validate-gstin", json={"gstin": "29AAAAA0000A1Z5"})
    assert r.status_code == 401
