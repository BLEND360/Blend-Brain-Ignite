"""Dependency-inversion ports for Phase 6 infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.domain import (
        ExpertMatch,
        IntelligenceScope,
        KnowledgeGraphSnapshot,
        ProjectIntelligenceRecord,
        SimilarProject,
    )


class KnowledgeGraphRepository(Protocol):
    """Persist complete graph projections atomically."""

    def replace(self, snapshot: KnowledgeGraphSnapshot) -> None:
        """Upsert nodes and replace one DNA version's edges."""
        ...


class IntelligenceCorpusRepository(Protocol):
    """Load current project vectors and graph attributes within a scope."""

    def load(self, scope: IntelligenceScope) -> tuple[ProjectIntelligenceRecord, ...]:
        """Return an immutable authorized corpus."""
        ...


class IntelligenceQueryEmbeddingGateway(Protocol):
    """Generate a semantic vector for an Expert Finder query."""

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Return one finite vector aligned with Project DNA embeddings."""
        ...


class IntelligenceIndex(Protocol):
    """Search one immutable authorized project intelligence snapshot."""

    def similar_projects(self, project_id: str, *, limit: int) -> tuple[SimilarProject, ...]:
        """Return explainable similar projects."""
        ...

    def find_experts(
        self,
        query: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[ExpertMatch, ...]:
        """Return evidence-backed expert candidates."""
        ...


class IntelligenceIndexFactory(Protocol):
    """Build immutable FAISS intelligence indexes."""

    def build(self, records: tuple[ProjectIntelligenceRecord, ...]) -> IntelligenceIndex:
        """Build a read projection."""
        ...
