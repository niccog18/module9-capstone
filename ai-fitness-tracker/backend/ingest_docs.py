"""Load the fitness documents into ChromaDB.

Usage (from the backend directory / inside the backend container):

    python ingest_docs.py            # add new and changed chunks, drop stale ones
    python ingest_docs.py --reset    # delete the collection and rebuild it
    python ingest_docs.py --docs-dir ../docs

The command is safe to run repeatedly: chunk IDs are stable
("<filename>:<chunk index>"), so unchanged text is simply overwritten, edited
text is updated, and chunks that no longer exist in the documents are removed.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_config import get_rag_settings
from rag_store import get_collection

REFERENCE_PREFIXES = ("reference:", "references:")


@dataclass(frozen=True)
class Chunk:
    """One retrievable piece of a source document."""

    chunk_id: str
    text: str
    source: str
    index: int


@dataclass(frozen=True)
class IngestSummary:
    documents: int
    chunks: int
    removed: int


def load_documents(docs_dir: Path) -> list[tuple[str, str]]:
    """Return (filename, text) for every .txt file in the directory."""

    if not docs_dir.is_dir():
        raise FileNotFoundError(f"Documents directory not found: {docs_dir}")

    return [
        (path.name, path.read_text(encoding="utf-8"))
        for path in sorted(docs_dir.glob("*.txt"))
    ]


def chunk_document(filename: str, text: str) -> list[Chunk]:
    """Split a document into paragraph chunks.

    Paragraphs are separated by blank lines (Windows or Unix line endings).
    Reference paragraphs are skipped: they describe where the content came
    from but are not useful as answer context.
    """

    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    chunks: list[Chunk] = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph or paragraph.lower().startswith(REFERENCE_PREFIXES):
            continue

        index = len(chunks)
        chunks.append(
            Chunk(
                chunk_id=f"{filename}:{index}",
                text=paragraph,
                source=filename,
                index=index,
            )
        )

    return chunks


def ingest(collection: Any, chunks: list[Chunk]) -> int:
    """Upsert chunks and delete stale ones. Return the number removed."""

    collection.upsert(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        metadatas=[
            {"source": chunk.source, "chunk_index": chunk.index} for chunk in chunks
        ],
    )

    current_ids = {chunk.chunk_id for chunk in chunks}
    stale_ids = sorted(set(collection.get(include=[])["ids"]) - current_ids)

    if stale_ids:
        collection.delete(ids=stale_ids)

    return len(stale_ids)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--docs-dir",
        type=Path,
        help="Folder of .txt documents (default: DOCS_DIRECTORY setting).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing collection before ingesting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    docs_dir = args.docs_dir or Path(get_rag_settings().docs_directory)

    try:
        documents = load_documents(docs_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    chunks = [
        chunk
        for filename, text in documents
        for chunk in chunk_document(filename, text)
    ]

    if not chunks:
        print(f"Error: no .txt content found in {docs_dir}.", file=sys.stderr)
        return 1

    print(f"Loaded {len(documents)} documents -> {len(chunks)} chunks.")
    print("Embedding chunks (the first run downloads the embedding model)...")

    collection = get_collection(reset=args.reset)
    removed = ingest(collection, chunks)

    print(
        f"Done: {len(chunks)} chunks in collection "
        f"'{collection.name}' ({removed} stale removed, "
        f"{collection.count()} total)."
    )
    print(
        "If the backend is already running, restart it so it picks up the new "
        "data: docker compose restart backend"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
