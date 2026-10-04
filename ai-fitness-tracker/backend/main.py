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
from rag_health import HEALTHY, UNHEALTHY, check_chroma, check_ollama
from routers.ask import router as ask_router
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
    """Report the status of the database, ChromaDB and Ollama.

    - healthy: every dependency is reachable (200).
    - degraded: the database works but ChromaDB or Ollama does not, so
      workouts and plans work while /ask does not (200).
    - unhealthy: the database is unreachable (503), so load balancers and
      orchestrators can detect a broken instance.
    """

    try:
        db.execute(select(1))
        database_status = HEALTHY
    except SQLAlchemyError:
        logger.exception("Database health check failed.")
        database_status = UNHEALTHY

    chroma_status = check_chroma()
    ollama_status = check_ollama()

    if database_status != HEALTHY:
        overall_status = UNHEALTHY
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif HEALTHY == chroma_status == ollama_status:
        overall_status = HEALTHY
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        database=database_status,
        ollama=ollama_status,
        chromadb=chroma_status,
    )


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api/v1")
app.include_router(exercises_router, prefix="/api/v1")
app.include_router(workouts_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")