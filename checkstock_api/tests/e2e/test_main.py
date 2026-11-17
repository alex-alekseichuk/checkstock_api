"""E2E test for the service health endpoint."""

from fastapi.testclient import TestClient


def test_ping_returns_ok(client: TestClient) -> None:
    """GET /ping responds 200 with the expected payload."""
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}
