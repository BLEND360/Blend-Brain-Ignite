"""Phase 4 OpenAI adapter tests without network calls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from openai import APIConnectionError, OpenAI

from blend_brain.knowledge_retrieval.domain import AnswerGenerationError, QueryEmbeddingError
from blend_brain.knowledge_retrieval.infrastructure.openai_answering import (
    AnswerClaimResponse,
    CitationResponse,
    GroundedAnswerResponse,
    OpenAIAnswerGenerator,
)
from blend_brain.knowledge_retrieval.infrastructure.openai_query_embeddings import (
    OpenAIQueryEmbeddingGateway,
)
from tests.unit.knowledge_retrieval.helpers import hit


class CharacterCounter:
    """Deterministic offline token counter."""

    def count(self, text: str) -> int:
        return len(text)


class FakeResponses:
    """Minimal Responses resource."""

    def __init__(self, parsed: GroundedAnswerResponse | None) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeEmbeddings:
    """Minimal embeddings resource."""

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
                SimpleNamespace(index=index, embedding=value)
                for index, value in enumerate(self.vectors)
            ]
        )


def client(
    *, responses: FakeResponses | None = None, embeddings: FakeEmbeddings | None = None
) -> OpenAI:
    """Cast a narrow test double at the SDK boundary."""
    return cast("OpenAI", SimpleNamespace(responses=responses, embeddings=embeddings))


def response() -> GroundedAnswerResponse:
    """Return a valid structured answer response."""
    return GroundedAnswerResponse(
        answerable=True,
        claims=[
            AnswerClaimResponse(
                text="Planning time fell by 30%.",
                citations=[CitationResponse(source_id="S1", quote="planning time by 30%")],
            )
        ],
        reason=None,
    )


def test_answer_generator_uses_structured_outputs_and_untrusted_context() -> None:
    responses = FakeResponses(response())
    generator = OpenAIAnswerGenerator(client(responses=responses), token_counter=CharacterCounter())

    result = generator.generate("What improved?", (hit(),))

    assert result.claims[0].citations[0].source_id == "S1"
    assert responses.calls[0]["text_format"] is GroundedAnswerResponse
    assert "UNTRUSTED_RETRIEVAL_JSON" in responses.calls[0]["input"][1]["content"]


def test_answer_generator_handles_empty_oversized_and_api_failures() -> None:
    empty = OpenAIAnswerGenerator(
        client(responses=FakeResponses(None)), token_counter=CharacterCounter()
    )
    with pytest.raises(AnswerGenerationError, match="no parsed"):
        empty.generate("Question?", (hit(),))

    oversized = OpenAIAnswerGenerator(
        client(responses=FakeResponses(response())),
        max_input_tokens=1,
        token_counter=CharacterCounter(),
    )
    with pytest.raises(AnswerGenerationError, match="token limit"):
        oversized.generate("Question?", (hit(),))

    responses = FakeResponses(response())
    responses.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    failing = OpenAIAnswerGenerator(client(responses=responses), token_counter=CharacterCounter())
    with pytest.raises(AnswerGenerationError):
        failing.generate("Question?", (hit(),))
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIAnswerGenerator(client(responses=responses), max_input_tokens=0)


def test_query_embeddings_validate_shape_tokens_and_failures() -> None:
    embeddings = FakeEmbeddings([[1.0, 2.0, 3.0]])
    gateway = OpenAIQueryEmbeddingGateway(
        client(embeddings=embeddings), dimensions=3, token_counter=CharacterCounter()
    )
    assert gateway.embed_query("query") == (1.0, 2.0, 3.0)
    assert embeddings.calls[0]["dimensions"] == 3

    with pytest.raises(QueryEmbeddingError, match="token limit"):
        OpenAIQueryEmbeddingGateway(
            client(embeddings=embeddings),
            dimensions=3,
            max_input_tokens=1,
            token_counter=CharacterCounter(),
        ).embed_query("query")

    for vectors in ([], [[1.0]], [[float("nan"), 2.0, 3.0]], [[0.0, 0.0, 0.0]]):
        with pytest.raises(QueryEmbeddingError):
            OpenAIQueryEmbeddingGateway(
                client(embeddings=FakeEmbeddings(vectors)),
                dimensions=3,
                token_counter=CharacterCounter(),
            ).embed_query("q")

    embeddings.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(QueryEmbeddingError):
        gateway.embed_query("query")
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIQueryEmbeddingGateway(client(embeddings=embeddings), dimensions=0)
