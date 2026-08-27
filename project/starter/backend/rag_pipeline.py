"""
Capstone Backend — RAG Pipeline  (STARTER)
=============================================
Implement retrieval (ChromaDB) and generation (Ollama or an API-based LLM)
here, then call these functions from your /ask (or equivalent) endpoint
in main.py.

Required:
    - Document ingestion: load ./docs, chunk, embed, store in ChromaDB
    - Retrieval: query ChromaDB, return top-N chunks with sources/distances
    - Generation: build a grounded prompt from retrieved context, call the LLM
    - At least one guardrail (confidence threshold, "I don't know" fallback,
      or similar) — see Module 9 grading rubric, "AI Integration"

TODO: implement ingest_documents(), retrieve(), and generate_answer().
"""

# TODO: import chromadb, requests (for Ollama), etc.

# TODO: def ingest_documents(docs_dir: str) -> int: ...
# TODO: def retrieve(question: str, n_results: int = 3) -> list: ...
# TODO: def generate_answer(question: str, context_chunks: list) -> str: ...
