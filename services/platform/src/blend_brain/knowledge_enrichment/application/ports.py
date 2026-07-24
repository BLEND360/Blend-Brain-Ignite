"""Dependency-inversion ports for external AI and persistence services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import ExtractedDocument
    from blend_brain.knowledge_enrichment.domain import (
        DocumentProfile,
        EmbeddingRecord,
        EmbeddingTarget,
        EnrichmentBundle,
        ProjectDNA,
    )


class ProjectDNAGenerator(Protocol):
    """Generate evidence-backed project intelligence."""

    def generate(
        self,
        project_id: str,
        profile: DocumentProfile,
        document: ExtractedDocument,
    ) -> ProjectDNA:
        """Generate and validate one Project DNA version."""
        ...


class EmbeddingGateway(Protocol):
    """Generate vectors for normalized targets."""

    def embed(self, targets: tuple[EmbeddingTarget, ...]) -> tuple[EmbeddingRecord, ...]:
        """Return one ordered embedding record per target."""
        ...


class KnowledgeRepository(Protocol):
    """Persist a complete enrichment bundle atomically."""

    def persist(self, bundle: EnrichmentBundle) -> None:
        """Commit one idempotent Phase 3 result."""
        ...
