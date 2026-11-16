"""Tests for the checkstock API routes."""

from fastapi.testclient import TestClient

from checkstock_api.main import app

client = TestClient(app)


def test_ping_returns_ok() -> None:
    """GET /ping responds 200 with the expected payload."""
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}
