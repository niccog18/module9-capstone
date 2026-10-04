"""RAG configuration, read from environment variables.

Settings are read lazily (on first use), not at import time, so importing the
application never fails or slows down because of RAG configuration, and tests
can change the environment and call ``get_rag_settings.cache_clear()``.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class RagSettings:
    """Validated settings for the retrieval-augmented assistant."""

    ollama_url: str
    model_name: str
    ollama_timeout_seconds: float
    chroma_path: str
    collection_name: str
    docs_directory: str
    confidence_threshold: float
    top_k: int


def _read_number(
    name: str,
    default: str,
    cast: type[int] | type[float],
    *,
    minimum: float,
    maximum: float,
) -> int | float:
    """Read a numeric environment variable and validate its range."""

    raw_value = os.getenv(name, default).strip()

    try:
        value = cast(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw_value!r}.") from exc

    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")

    return value


@lru_cache
def get_rag_settings() -> RagSettings:
    """Return validated RAG settings (cached after the first call)."""

    model_name = os.getenv("MODEL_NAME", "llama3.2:3b").strip()

    if not model_name:
        raise ValueError("MODEL_NAME must not be empty.")

    return RagSettings(
        ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434").strip().rstrip("/"),
        model_name=model_name,
        ollama_timeout_seconds=float(
            _read_number("OLLAMA_TIMEOUT_SECONDS", "120", float, minimum=1, maximum=600)
        ),
        chroma_path=os.getenv("CHROMA_PATH", "/app/chroma_data").strip(),
        collection_name=os.getenv("COLLECTION_NAME", "fitness_docs").strip(),
        docs_directory=os.getenv("DOCS_DIRECTORY", "docs").strip(),
        # Minimum cosine similarity (0-1) a chunk needs to be used as context.
        confidence_threshold=float(
            _read_number("CONFIDENCE_THRESHOLD", "0.30", float, minimum=0, maximum=1)
        ),
        top_k=int(_read_number("TOP_K", "4", int, minimum=1, maximum=20)),
    )
