"""Tests for the /health endpoint.

ChromaDB and Ollama checks are replaced with fixed answers, so no real
services are needed. The database check uses the per-test SQLite database.
"""

import pytest
from sqlalchemy.exc import SQLAlchemyError

import main
from database import get_db
from main import app
from rag_health import HEALTHY, UNHEALTHY


@pytest.fixture()
def set_services(monkeypatch):
    """Return a function that fixes the ChromaDB and Ollama check results."""

    def _set(chroma=HEALTHY, ollama=HEALTHY):
        monkeypatch.setattr(main, "check_chroma", lambda: chroma)
        monkeypatch.setattr(main, "check_ollama", lambda: ollama)

    return _set


def test_health_is_healthy_when_every_service_is_up(client, set_services):
    """All dependencies reachable: 200 and an overall 'healthy'."""

    set_services()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "healthy",
        "chromadb": "healthy",
        "ollama": "healthy",
    }


def test_health_is_degraded_when_ollama_is_down(client, set_services):
    """The database works but Ollama does not: still 200, reported as degraded."""

    set_services(ollama=UNHEALTHY)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "healthy"
    assert body["ollama"] == "unhealthy"


def test_health_is_unhealthy_when_the_database_is_down(client, set_services):
    """An unreachable database is a 503 so orchestrators can detect it."""

    set_services()

    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("database is down")

    def broken_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_get_db

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "unhealthy"