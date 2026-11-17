"""E2E tests for the service health endpoint and the Swagger UI."""

from fastapi.testclient import TestClient


def test_ping_returns_ok(client: TestClient) -> None:
    """GET /ping responds 200 with the expected payload."""
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "pong"}


def test_root_redirects_to_docs(client: TestClient) -> None:
    """GET / redirects to the Swagger UI page."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_docs_serves_swagger_ui(client: TestClient) -> None:
    """GET /docs responds 200 with the Swagger UI HTML page."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # The page boots Swagger UI against the OpenAPI schema.
    assert 'dom_id: "#swagger-ui"' in response.text
    assert 'url: "/openapi.json"' in response.text


def test_openapi_schema_available(client: TestClient) -> None:
    """GET /openapi.json returns the OpenAPI document."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "checkstock API"
