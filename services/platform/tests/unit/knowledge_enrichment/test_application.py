"""Metadata, target, and orchestration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from blend_brain.knowledge_enrichment.application import (
    EmbeddingTargetFactory,
    KnowledgeEnrichmentService,
    MetadataExtractionService,
)
from blend_brain.knowledge_enrichment.domain import EmbeddingTargetType
from tests.unit.knowledge_enrichment.helpers import NOW, dna, document

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import ExtractedDocument
    from blend_brain.knowledge_enrichment.application import (
        EmbeddingGateway,
        KnowledgeRepository,
        ProjectDNAGenerator,
    )
    from blend_brain.knowledge_enrichment.domain import (
        DocumentProfile,
        EmbeddingRecord,
        EmbeddingTarget,
        EnrichmentBundle,
        ProjectDNA,
    )


def test_metadata_is_deterministic_and_complete() -> None:
    extractor = MetadataExtractionService()

    first = extractor.extract(document())
    second = extractor.extract(document())

    assert first == second
    assert first.title == "Retail Forecasting"
    assert first.section_count == 2
    assert first.character_count == len(document().text)
    assert first.word_count == len(document().text.split())


def test_embedding_targets_are_stable_and_include_project_dna() -> None:
    source = document()
    profile = MetadataExtractionService().extract(source)
    targets = EmbeddingTargetFactory().create("project-1", profile, source, dna())

    assert len(targets) == 3
    assert targets[0].target_type is EmbeddingTargetType.DOCUMENT_SECTION
    assert targets[-1].target_type is EmbeddingTargetType.PROJECT_DNA
    assert targets == EmbeddingTargetFactory().create("project-1", profile, source, dna())


def test_pipeline_coordinates_and_persists_one_bundle() -> None:
    generated_dna = dna()

    class DNAGenerator:
        def generate(
            self,
            _project_id: str,
            _profile: DocumentProfile,
            _document: ExtractedDocument,
        ) -> ProjectDNA:
            return generated_dna

    class Embeddings:
        received: tuple[EmbeddingTarget, ...] = ()

        def embed(self, targets: tuple[EmbeddingTarget, ...]) -> tuple[EmbeddingRecord, ...]:
            self.received = targets
            return ()

    class Repository:
        persisted: EnrichmentBundle | None = None

        def persist(self, bundle: EnrichmentBundle) -> None:
            self.persisted = bundle

    embeddings = Embeddings()
    repository = Repository()
    service = KnowledgeEnrichmentService(
        DNAGenerator(),
        embeddings,
        repository,
        clock=lambda: NOW,
        run_id_factory=lambda: "run-id",
    )

    result = service.enrich(" project-1 ", document())

    assert result.run_id == "run-id"
    assert result.project_id == "project-1"
    assert repository.persisted is result
    assert len(embeddings.received) == 3


def test_pipeline_rejects_empty_project_id() -> None:
    service = KnowledgeEnrichmentService(
        cast("ProjectDNAGenerator", object()),
        cast("EmbeddingGateway", object()),
        cast("KnowledgeRepository", object()),
    )
    with pytest.raises(ValueError, match="project_id"):
        service.enrich(" ", document())
