"""Expert Finder embedding adapter tests without network calls."""

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from openai import APIConnectionError, OpenAI

from blend_brain.organizational_intelligence.domain import IntelligenceEmbeddingError
from blend_brain.organizational_intelligence.infrastructure.openai_embeddings import (
    OpenAIIntelligenceEmbeddingGateway,
)


class Counter:
    """Deterministic character counter."""

    def count(self, text: str) -> int:
        return len(text)


class Embeddings:
    """Minimal OpenAI embeddings resource."""

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=vector)
                for index, vector in enumerate(self.vectors)
            ]
        )


def client(embeddings: Embeddings) -> OpenAI:
    """Cast a narrow test double at the SDK boundary."""
    return cast("OpenAI", SimpleNamespace(embeddings=embeddings))


def test_embedding_gateway_uses_configured_project_dna_space() -> None:
    embeddings = Embeddings([[1.0, 2.0, 3.0]])
    gateway = OpenAIIntelligenceEmbeddingGateway(
        client(embeddings), dimensions=3, token_counter=Counter()
    )

    assert gateway.embed_query("Snowflake expert") == (1.0, 2.0, 3.0)
    assert embeddings.calls[0]["model"] == "text-embedding-3-large"
    assert embeddings.calls[0]["dimensions"] == 3


def test_embedding_gateway_rejects_limits_failures_and_invalid_vectors() -> None:
    embeddings = Embeddings([[1.0, 2.0, 3.0]])
    with pytest.raises(IntelligenceEmbeddingError, match="token limit"):
        OpenAIIntelligenceEmbeddingGateway(
            client(embeddings), dimensions=3, max_input_tokens=1, token_counter=Counter()
        ).embed_query("query")

    embeddings.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(IntelligenceEmbeddingError, match="failed"):
        OpenAIIntelligenceEmbeddingGateway(
            client(embeddings), dimensions=3, token_counter=Counter()
        ).embed_query("q")

    for vectors in ([], [[1.0]], [[float("nan"), 0.0, 0.0]], [[0.0, 0.0, 0.0]]):
        with pytest.raises(IntelligenceEmbeddingError):
            OpenAIIntelligenceEmbeddingGateway(
                client(Embeddings(vectors)), dimensions=3, token_counter=Counter()
            ).embed_query("q")
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIIntelligenceEmbeddingGateway(client(embeddings), dimensions=0)
