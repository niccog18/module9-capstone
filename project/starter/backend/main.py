"""FastAPI application and API endpoints for the fitness tracking application."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import Base, engine
from dependencies import DatabaseSession
from routers.auth import router as auth_router
from routers.exercises import router as exercises_router
from routers.plans import router as plans_router
from routers.workouts import router as workouts_router
from schemas import HealthResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
    if origin.strip()
]


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources.

    Table creation is intended for development. Use Alembic migrations in
    production.
    """

    Base.metadata.create_all(bind=engine)

    yield


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Fitness Tracker API",
    description=(
        "A professional fitness tracking API for managing workouts, "
        "exercises, workout plans, authentication, and AI-assisted fitness "
        "information."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Authentication uses a bearer token in the Authorization header, not
# cookies, so credentialed cross-origin requests are not needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Root and health endpoints
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
def read_root() -> dict[str, str]:
    """Return basic API information."""

    return {
        "name": "Fitness Tracker API",
        "version": app.version,
        "status": "running",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
)
def health_check(
    response: Response,
    db: DatabaseSession,
) -> HealthResponse:
    """Check whether the API and database are available.

    Returns 503 when the database is unreachable so load balancers and
    orchestrators can detect an unhealthy instance.
    """

    try:
        db.execute(select(1))
        database_status = "healthy"
    except SQLAlchemyError:
        logger.exception("Database health check failed.")
        database_status = "unhealthy"

    if database_status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=database_status,
        database=database_status,
        ollama="not_checked",
        chromadb="not_checked",
    )


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api/v1")
app.include_router(exercises_router, prefix="/api/v1")
app.include_router(workouts_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")