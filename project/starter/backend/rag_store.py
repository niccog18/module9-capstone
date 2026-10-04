"""ChromaDB access shared by document ingestion and question answering.

Both sides must open the collection the same way (same embedding function,
same distance metric), so that logic lives here. chromadb is imported lazily
so importing this module stays cheap and works in environments without it.
"""

from functools import lru_cache
from typing import Any

from rag_config import get_rag_settings


@lru_cache
def _get_client(chroma_path: str) -> Any:
    import chromadb

    return chromadb.PersistentClient(path=chroma_path)


def get_collection(*, reset: bool = False) -> Any:
    """Return the fitness documents collection, creating it if needed.

    The collection uses cosine distance, so ``similarity = 1 - distance``.
    Embeddings come from chromadb's built-in ONNX all-MiniLM-L6-v2 model.
    With ``reset=True`` any existing collection is deleted first, which is
    required if the distance metric or embedding model ever changes.
    """

    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    settings = get_rag_settings()
    client = _get_client(settings.chroma_path)

    if reset:
        try:
            from chromadb.errors import NotFoundError as missing_error
        except ImportError:
            missing_error = ValueError

        try:
            client.delete_collection(settings.collection_name)
        except (missing_error, ValueError):
            pass  # nothing to delete

    return client.get_or_create_collection(
        name=settings.collection_name,
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )