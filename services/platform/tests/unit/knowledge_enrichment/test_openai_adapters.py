"""OpenAI adapter tests without external network calls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
from openai import APIConnectionError, OpenAI

from blend_brain.knowledge_enrichment.application import (
    EmbeddingTargetFactory,
    MetadataExtractionService,
)
from blend_brain.knowledge_enrichment.domain import (
    EmbeddingGenerationError,
    EnrichmentInputTooLargeError,
    ProjectDNAGenerationError,
)
from blend_brain.knowledge_enrichment.infrastructure.openai_embeddings import (
    OpenAIEmbeddingGateway,
)
from blend_brain.knowledge_enrichment.infrastructure.openai_project_dna import (
    ClaimResponse,
    EvidenceResponse,
    OpenAIProjectDNAGenerator,
    ProjectDNAResponse,
)
from tests.unit.knowledge_enrichment.helpers import NOW, dna, document

if TYPE_CHECKING:
    from blend_brain.knowledge_enrichment.domain import EmbeddingTarget


class CharacterTokenCounter:
    """Deterministic offline token counter for workflow tests."""

    def count(self, text: str) -> int:
        return len(text)


TOKEN_COUNTER = CharacterTokenCounter()


def project_dna_response(*, quote: str = "Retail Forecasting") -> ProjectDNAResponse:
    """Return a strict structured-output response."""
    project = ClaimResponse(
        value="Retail Forecasting",
        confidence="high",
        evidence=[EvidenceResponse(section_sequence=1, quote=quote)],
    )
    technology = ClaimResponse(
        value="Snowflake",
        confidence="high",
        evidence=[EvidenceResponse(section_sequence=2, quote="Snowflake")],
    )
    return ProjectDNAResponse(
        project_name=project,
        client_name=None,
        industry=None,
        engagement_type=None,
        summary=project,
        business_challenges=[],
        use_cases=[],
        capabilities=[],
        technologies=[technology],
        data_sources=[],
        cloud_platforms=[],
        outcomes=[],
        differentiators=[],
        experts=[],
    )


class FakeResponses:
    """Minimal responses resource."""

    def __init__(self, parsed: ProjectDNAResponse | list[ProjectDNAResponse | None] | None) -> None:
        self.results = parsed if isinstance(parsed, list) else [parsed]
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        result_index = min(len(self.calls) - 1, len(self.results) - 1)
        return SimpleNamespace(output_parsed=self.results[result_index])


class FakeEmbeddings:
    """Minimal embeddings resource with configurable results."""

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        data = [
            SimpleNamespace(index=index, embedding=vector)
            for index, vector in reversed(tuple(enumerate(self.vectors)))
        ]
        return SimpleNamespace(data=data)


def fake_client(
    *, responses: FakeResponses | None = None, embeddings: FakeEmbeddings | None = None
) -> OpenAI:
    """Cast a test double to the SDK client boundary."""
    return cast("OpenAI", SimpleNamespace(responses=responses, embeddings=embeddings))


def embedding_targets() -> tuple[EmbeddingTarget, ...]:
    """Build real application embedding targets."""
    source = document()
    profile = MetadataExtractionService().extract(source)
    return EmbeddingTargetFactory().create("project-1", profile, source, dna())[:2]


def test_project_dna_uses_structured_outputs_and_validates_evidence() -> None:
    responses = FakeResponses(project_dna_response())
    generator = OpenAIProjectDNAGenerator(
        fake_client(responses=responses),
        clock=lambda: NOW,
        token_counter=TOKEN_COUNTER,
    )

    result = generator.generate(
        "project-1", MetadataExtractionService().extract(document()), document()
    )

    assert result.project_name is not None
    assert result.project_name.value == "Retail Forecasting"
    assert result.technologies[0].value == "Snowflake"
    assert responses.calls[0]["text_format"] is ProjectDNAResponse
    assert "untrusted" in responses.calls[0]["input"][1]["content"]


def test_project_dna_discards_ungrounded_claims_after_retry() -> None:
    profile = MetadataExtractionService().extract(document())
    responses = FakeResponses(project_dna_response(quote="invented"))
    ungrounded = OpenAIProjectDNAGenerator(
        fake_client(responses=responses),
        token_counter=TOKEN_COUNTER,
    )
    result = ungrounded.generate("project-1", profile, document())

    assert result.project_name is None
    assert result.summary is None
    assert result.technologies[0].value == "Snowflake"
    assert len(responses.calls) == 2


def test_project_dna_rejects_empty_and_oversized_results() -> None:
    profile = MetadataExtractionService().extract(document())

    empty = OpenAIProjectDNAGenerator(
        fake_client(responses=FakeResponses(None)), token_counter=TOKEN_COUNTER
    )
    with pytest.raises(ProjectDNAGenerationError):
        empty.generate("project-1", profile, document())

    oversized = OpenAIProjectDNAGenerator(
        fake_client(responses=FakeResponses(project_dna_response())),
        max_input_tokens=1,
        token_counter=TOKEN_COUNTER,
    )
    with pytest.raises(EnrichmentInputTooLargeError):
        oversized.generate("project-1", profile, document())


def test_project_dna_retries_only_failed_literal_grounding() -> None:
    responses = FakeResponses([project_dna_response(quote="invented"), project_dna_response()])
    generator = OpenAIProjectDNAGenerator(
        fake_client(responses=responses), token_counter=TOKEN_COUNTER
    )

    result = generator.generate(
        "project-1", MetadataExtractionService().extract(document()), document()
    )

    assert result.project_name is not None
    assert len(responses.calls) == 2
    assert "previous response failed" in responses.calls[1]["input"][0]["content"].lower()


def test_project_dna_translates_openai_failure_and_validates_limits() -> None:
    responses = FakeResponses(project_dna_response())
    responses.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    generator = OpenAIProjectDNAGenerator(
        fake_client(responses=responses), token_counter=TOKEN_COUNTER
    )
    with pytest.raises(ProjectDNAGenerationError):
        generator.generate("project-1", MetadataExtractionService().extract(document()), document())
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIProjectDNAGenerator(
            fake_client(responses=responses),
            max_input_tokens=0,
            token_counter=TOKEN_COUNTER,
        )
    with pytest.raises(ValueError, match="between 1 and 3"):
        OpenAIProjectDNAGenerator(
            fake_client(responses=responses),
            grounding_attempts=0,
            token_counter=TOKEN_COUNTER,
        )


def test_embeddings_preserve_order_batch_and_dimensions() -> None:
    embeddings = FakeEmbeddings([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    gateway = OpenAIEmbeddingGateway(
        fake_client(embeddings=embeddings),
        dimensions=3,
        clock=lambda: NOW,
        token_counter=TOKEN_COUNTER,
    )

    records = gateway.embed(embedding_targets())

    assert records[0].vector == (1.0, 2.0, 3.0)
    assert records[1].vector == (4.0, 5.0, 6.0)
    assert embeddings.calls[0]["model"] == "text-embedding-3-large"
    assert embeddings.calls[0]["encoding_format"] == "float"


def test_embeddings_handle_empty_batching_and_token_limits() -> None:
    targets = embedding_targets()
    embeddings = FakeEmbeddings([[1.0]])
    gateway = OpenAIEmbeddingGateway(
        fake_client(embeddings=embeddings),
        dimensions=1,
        batch_size=1,
        token_counter=TOKEN_COUNTER,
    )
    assert gateway.embed(()) == ()
    gateway.embed(targets)
    assert len(embeddings.calls) == 2

    limited = OpenAIEmbeddingGateway(
        fake_client(embeddings=embeddings),
        dimensions=1,
        max_input_tokens=1,
        token_counter=TOKEN_COUNTER,
    )
    with pytest.raises(EnrichmentInputTooLargeError):
        limited.embed(targets)


@pytest.mark.parametrize("vectors", [[], [[1.0]], [[float("nan"), 2.0, 3.0]]])
def test_embeddings_reject_invalid_responses(vectors: list[list[float]]) -> None:
    gateway = OpenAIEmbeddingGateway(
        fake_client(embeddings=FakeEmbeddings(vectors)),
        dimensions=3,
        token_counter=TOKEN_COUNTER,
    )
    with pytest.raises(EmbeddingGenerationError):
        gateway.embed(embedding_targets())


def test_embeddings_translate_api_failures_and_validate_configuration() -> None:
    embeddings = FakeEmbeddings([[1.0]])
    embeddings.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    gateway = OpenAIEmbeddingGateway(
        fake_client(embeddings=embeddings),
        dimensions=1,
        token_counter=TOKEN_COUNTER,
    )
    with pytest.raises(EmbeddingGenerationError):
        gateway.embed(embedding_targets())
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIEmbeddingGateway(
            fake_client(embeddings=embeddings),
            dimensions=0,
            token_counter=TOKEN_COUNTER,
        )
    with pytest.raises(ValueError, match="2048"):
        OpenAIEmbeddingGateway(
            fake_client(embeddings=embeddings),
            batch_size=2049,
            token_counter=TOKEN_COUNTER,
        )
