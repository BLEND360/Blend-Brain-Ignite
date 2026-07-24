"""Phase 3 enrichment orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from blend_brain.knowledge_enrichment.application.metadata import MetadataExtractionService
from blend_brain.knowledge_enrichment.application.targets import EmbeddingTargetFactory
from blend_brain.knowledge_enrichment.domain import EnrichmentBundle

if TYPE_CHECKING:
    from collections.abc import Callable

    from blend_brain.document_ingestion.domain import ExtractedDocument
    from blend_brain.knowledge_enrichment.application.ports import (
        EmbeddingGateway,
        KnowledgeRepository,
        ProjectDNAGenerator,
    )


class KnowledgeEnrichmentService:
    """Coordinate pure metadata, AI enrichment, embeddings, and persistence."""

    def __init__(
        self,
        dna_generator: ProjectDNAGenerator,
        embedding_gateway: EmbeddingGateway,
        repository: KnowledgeRepository,
        *,
        metadata_extractor: MetadataExtractionService | None = None,
        target_factory: EmbeddingTargetFactory | None = None,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._dna_generator = dna_generator
        self._embedding_gateway = embedding_gateway
        self._repository = repository
        self._metadata_extractor = metadata_extractor or MetadataExtractionService()
        self._target_factory = target_factory or EmbeddingTargetFactory()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._run_id_factory = run_id_factory or (lambda: str(uuid4()))

    def enrich(self, project_id: str, document: ExtractedDocument) -> EnrichmentBundle:
        """Execute Phase 3 and atomically persist its completed result."""
        normalized_project_id = project_id.strip()
        if not normalized_project_id:
            raise ValueError("project_id must not be empty")
        profile = self._metadata_extractor.extract(document)
        project_dna = self._dna_generator.generate(normalized_project_id, profile, document)
        targets = self._target_factory.create(
            normalized_project_id,
            profile,
            document,
            project_dna,
        )
        embeddings = self._embedding_gateway.embed(targets)
        bundle = EnrichmentBundle(
            run_id=self._run_id_factory(),
            project_id=normalized_project_id,
            document=document,
            profile=profile,
            project_dna=project_dna,
            embeddings=embeddings,
            completed_at=self._clock(),
        )
        self._repository.persist(bundle)
        return bundle
