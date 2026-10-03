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
def client():
    """Return a TestClient backed by a fresh in-memory database."""

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
    testing_session = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Deliberately not used as a context manager: that would run the app
    # lifespan, which targets the real database.
    yield TestClient(app)

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()