"""AI assistant endpoint: fitness questions answered from the document corpus."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from auth import CurrentUser
from rag_pipeline import RagUnavailableError, rag_query
from rag_store import get_collection
from schemas import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ask",
    tags=["AI Assistant"],
)


def get_rag_collection() -> Any:
    """Open the ChromaDB collection, or answer 503 if it cannot be opened.

    A dependency so tests can replace it with a fake collection.
    """

    try:
        return get_collection()
    except Exception as exc:  # chromadb can fail in many ways; do not leak them
        logger.exception("Could not open the ChromaDB collection.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The knowledge base is not available.",
        ) from exc


RagCollection = Annotated[Any, Depends(get_rag_collection)]


@router.post(
    "",
    response_model=AskResponse,
)
def ask_question(
    request: AskRequest,
    current_user: CurrentUser,
    collection: RagCollection,
) -> dict[str, Any]:
    """Answer a fitness question using only the curated fitness documents.

    The response lists the documents used. When no document is relevant
    enough, the answer says so instead of guessing. Returns 503 when the
    knowledge base or the language model is unavailable.
    """

    try:
        return rag_query(request.question, collection=collection)
    except RagUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc