from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    with patch("app.api.routes.check_db_health", return_value=True):
        resp = client.get("/health")
    assert resp.status_code == 200


def test_health_response_has_status():
    with patch("app.api.routes.check_db_health", return_value=True):
        resp = client.get("/health")
    data = resp.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_health_response_has_db_connected():
    with patch("app.api.routes.check_db_health", return_value=True):
        resp = client.get("/health")
    data = resp.json()
    assert "db_connected" in data
    assert data["db_connected"] is True


def test_health_degraded_when_db_down():
    with patch("app.api.routes.check_db_health", return_value=False):
        resp = client.get("/health")
    data = resp.json()
    assert resp.status_code == 200
    assert data["status"] == "degraded"
    assert data["db_connected"] is False


def test_health_has_version():
    with patch("app.api.routes.check_db_health", return_value=True):
        resp = client.get("/health")
    data = resp.json()
    assert "version" in data


def test_search_stub():
    resp = client.post("/search", json={"query": "supply chain risks"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []


def test_ask_stub():
    resp = client.post("/ask", json={"question": "What are the main risks?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
