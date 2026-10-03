"""Shared pytest fixtures.

Each test gets its own empty in-memory SQLite database, swapped in for the
real PostgreSQL session through FastAPI's dependency overrides. Tests never
touch the Compose database and can be run any number of times.
"""

import os

# These must be set before the application modules are imported, because
# auth.py validates the JWT secret at import time and database.py reads
# DATABASE_URL. setdefault keeps real values if the container already has
# them. No connection to the placeholder URL is ever opened: get_db is
# overridden below.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-that-is-at-least-32-characters-long",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import models  # noqa: E402,F401  (registers every table on Base.metadata)
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture()
def session_factory():
    """Yield a sessionmaker bound to a fresh in-memory SQLite database."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection, so the DB persists per test
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    yield sessionmaker(bind=engine, autoflush=False)

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    """Return a TestClient whose database dependency uses the test database."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Deliberately not used as a context manager: that would run the app
    # lifespan, which targets the real database.
    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def make_auth_headers(client):
    """Return a function that registers a user and returns bearer headers."""

    def _make(username="pytest_user"):
        password = "TestPassword123!"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def auth_headers(make_auth_headers):
    """Bearer headers for a default registered user."""

    return make_auth_headers()