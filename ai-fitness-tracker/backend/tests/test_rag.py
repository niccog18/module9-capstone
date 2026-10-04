"""Capstone backend tests for the RAG endpoint (POST /api/v1/ask).

No real ChromaDB or Ollama is used: the collection is replaced with a fake
through FastAPI's dependency overrides, and Ollama's HTTP call is mocked.
"""

import httpx
import pytest

import rag_pipeline
from main import app
from rag_config import RagSettings
from rag_pipeline import NO_INFORMATION_ANSWER
from routers.ask import get_rag_collection

URL = "/api/v1/ask"
QUESTION = {"question": "How long should I rest between heavy sets?"}

REST_TEXT = "Rest 2 to 3 minutes between heavy sets."
TERMS_TEXT = "A set is a group of consecutive repetitions."


class FakeCollection:
    """Stands in for a Chroma collection; returns fixed chunks and distances."""

    def __init__(self, distances=(0.40, 0.55), count=10):
        self.distances = list(distances)
        self._count = count

    def count(self):
        return self._count

    def query(self, query_texts, n_results, include):
        documents = [REST_TEXT, TERMS_TEXT][: len(self.distances)]
        sources = ["rest_intervals.txt", "training_terminology.txt"]
        return {
            "documents": [documents],
            "metadatas": [[{"source": name} for name in sources[: len(documents)]]],
            "distances": [self.distances],
        }


@pytest.fixture(autouse=True)
def rag_settings(monkeypatch):
    """Pin RAG settings so tests do not depend on the container environment."""

    settings = RagSettings(
        ollama_url="http://ollama.test:11434",
        model_name="test-model",
        ollama_timeout_seconds=5.0,
        chroma_path="/unused",
        collection_name="unused",
        docs_directory="unused",
        confidence_threshold=0.30,
        top_k=4,
    )
    monkeypatch.setattr(rag_pipeline, "get_rag_settings", lambda: settings)


def use_collection(collection):
    app.dependency_overrides[get_rag_collection] = lambda: collection


def mock_ollama(monkeypatch, answer="Rest 2 to 3 minutes [rest_intervals.txt]."):
    """Mock Ollama's chat endpoint and return the list of captured requests."""

    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json})
        return httpx.Response(
            200,
            json={"message": {"content": answer}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(rag_pipeline.httpx, "post", fake_post)
    return calls


def test_ask_requires_auth(client):
    """The assistant endpoint rejects requests without a bearer token."""

    assert client.post(URL, json=QUESTION).status_code == 401


@pytest.mark.parametrize("question", ["", "   "])
def test_ask_rejects_empty_question(client, auth_headers, question):
    """Empty or whitespace-only questions fail validation."""

    response = client.post(URL, json={"question": question}, headers=auth_headers)

    assert response.status_code == 422


def test_ask_returns_answer_with_sources(client, auth_headers, monkeypatch):
    """A relevant question returns an answer, its sources and a confidence."""

    use_collection(FakeCollection(distances=(0.40, 0.55)))
    mock_ollama(monkeypatch)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "[rest_intervals.txt]" in data["answer"]
    assert [source["document"] for source in data["sources"]] == [
        "rest_intervals.txt",
        "training_terminology.txt",
    ]
    assert data["sources"][0]["content"] == REST_TEXT
    assert data["confidence"] == pytest.approx(0.60)
    assert data["chunks_retrieved"] == 2


def test_ask_handles_no_matching_documents(client, auth_headers, monkeypatch):
    """Irrelevant questions get the fallback answer and never call the LLM."""

    use_collection(FakeCollection(distances=(0.90, 0.95)))
    calls = mock_ollama(monkeypatch)

    response = client.post(
        URL, json={"question": "What is the capital of France?"}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == NO_INFORMATION_ANSWER
    assert data["sources"] == []
    assert data["confidence"] == 0.0
    assert data["chunks_retrieved"] == 0
    assert calls == []


def test_ask_only_uses_chunks_above_the_threshold(client, auth_headers, monkeypatch):
    """Chunks below the similarity threshold are not sent to the model."""

    use_collection(FakeCollection(distances=(0.40, 0.90)))
    calls = mock_ollama(monkeypatch)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.json()["chunks_retrieved"] == 1
    user_prompt = calls[0]["json"]["messages"][1]["content"]
    assert REST_TEXT in user_prompt
    assert TERMS_TEXT not in user_prompt


def test_ask_grounds_the_prompt_in_retrieved_context(client, auth_headers, monkeypatch):
    """The model gets the grounding rules, the context and the question."""

    use_collection(FakeCollection())
    calls = mock_ollama(monkeypatch)

    client.post(URL, json=QUESTION, headers=auth_headers)

    payload = calls[0]["json"]
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    system_prompt, user_prompt = (m["content"] for m in payload["messages"])
    assert "ONLY" in system_prompt
    assert "[rest_intervals.txt]" in user_prompt
    assert QUESTION["question"] in user_prompt


def test_ask_removes_invented_citations(client, auth_headers, monkeypatch):
    """Citations of files that were not retrieved are stripped from the answer."""

    use_collection(FakeCollection())
    mock_ollama(
        monkeypatch,
        answer="Rest 2 to 3 minutes [rest_intervals.txt] [made_up_file.txt].",
    )

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    answer = response.json()["answer"]
    assert "[rest_intervals.txt]" in answer
    assert "made_up_file" not in answer


def test_ask_returns_503_when_ollama_is_unreachable(client, auth_headers, monkeypatch):
    """An unreachable language model is a 503 that leaks no internal details."""

    use_collection(FakeCollection())

    def unreachable(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(rag_pipeline.httpx, "post", unreachable)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "ollama.test" not in detail
    assert "refused" not in detail


def test_ask_returns_503_when_ollama_times_out(client, auth_headers, monkeypatch):
    """A slow language model is a 503, not a hung request."""

    use_collection(FakeCollection())

    def too_slow(url, json, timeout):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(rag_pipeline.httpx, "post", too_slow)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.status_code == 503


def test_ask_returns_503_when_knowledge_base_is_empty(client, auth_headers, monkeypatch):
    """Asking before the documents are ingested is a 503, not a made-up answer."""

    use_collection(FakeCollection(count=0))
    calls = mock_ollama(monkeypatch)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.status_code == 503
    assert calls == []


def test_ask_drops_a_contradictory_dont_know(client, auth_headers, monkeypatch):
    """An 'I don't know' tacked onto a real answer is removed from the reply."""

    use_collection(FakeCollection())
    mock_ollama(
        monkeypatch,
        answer=(
            "Rest 2 to 3 minutes between heavy sets [rest_intervals.txt]. "
            "I don't know based on the provided documents."
        ),
    )

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    answer = response.json()["answer"]
    assert "2 to 3 minutes" in answer
    assert "don't know" not in answer


def test_ask_keeps_a_plain_dont_know(client, auth_headers, monkeypatch):
    """A reply that is only 'I don't know' is passed through unchanged."""

    use_collection(FakeCollection())
    mock_ollama(monkeypatch, answer="I don't know based on the provided documents.")

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.json()["answer"] == "I don't know based on the provided documents."


def test_ask_returns_503_when_the_vector_search_fails(client, auth_headers, monkeypatch):
    """A ChromaDB error during the search is a 503, not an unhandled 500."""

    class BrokenCollection(FakeCollection):
        def query(self, query_texts, n_results, include):
            raise RuntimeError("Error creating hnsw segment reader")

    use_collection(BrokenCollection())
    calls = mock_ollama(monkeypatch)

    response = client.post(URL, json=QUESTION, headers=auth_headers)

    assert response.status_code == 503
    assert calls == []