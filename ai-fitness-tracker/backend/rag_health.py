"""Dependency checks for the /health endpoint.

Each check returns "healthy" or "unhealthy" and never raises, so a failing
dependency can never turn the health endpoint itself into a 500.
"""

import logging

import httpx

from rag_config import get_rag_settings
from rag_store import get_collection

logger = logging.getLogger(__name__)

HEALTHY = "healthy"
UNHEALTHY = "unhealthy"

OLLAMA_CHECK_TIMEOUT_SECONDS = 2.0


def check_chroma() -> str:
    """Healthy when the collection opens and contains ingested chunks."""

    try:
        if get_collection().count() == 0:
            logger.info("ChromaDB is reachable but the collection is empty.")
            return UNHEALTHY
        return HEALTHY
    except Exception:  # chromadb can fail in many ways; report, do not raise
        logger.exception("ChromaDB health check failed.")
        return UNHEALTHY


def check_ollama() -> str:
    """Healthy when Ollama responds and the configured model is pulled."""

    try:
        settings = get_rag_settings()
        response = httpx.get(
            f"{settings.ollama_url}/api/tags",
            timeout=OLLAMA_CHECK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        available = {model["name"] for model in response.json().get("models", [])}
        wanted = settings.model_name
        if ":" not in wanted:
            wanted = f"{wanted}:latest"

        if wanted not in available:
            logger.info("Ollama is reachable but model %s is not pulled.", wanted)
            return UNHEALTHY

        return HEALTHY
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        # Logged briefly: Compose polls /health every few seconds, so a long
        # traceback here would flood the logs while Ollama is down.
        logger.info("Ollama health check failed: %s", exc)
        return UNHEALTHY