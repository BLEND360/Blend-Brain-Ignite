"""Dependency-inversion ports for retrieval infrastructure and AI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from blend_brain.knowledge_retrieval.domain import (
        GeneratedAnswerDraft,
        IndexedSection,
        RetrievalHit,
        RetrievalScope,
    )


class RetrievalCorpusRepository(Protocol):
    """Load only corpus rows allowed by an explicit project scope."""

    def load(self, scope: RetrievalScope) -> tuple[IndexedSection, ...]:
        """Return an immutable scoped corpus snapshot."""
        ...


class QueryEmbeddingGateway(Protocol):
    """Generate a semantic vector for one normalized query."""

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Return one finite vector."""
        ...


class HybridSearchIndex(Protocol):
    """Search one immutable corpus snapshot."""

    def search(
        self, query: str, query_embedding: tuple[float, ...], *, limit: int
    ) -> tuple[RetrievalHit, ...]:
        """Return results ordered by fused relevance."""
        ...


class HybridSearchIndexFactory(Protocol):
    """Build immutable hybrid indexes from durable corpus rows."""

    def build(self, sections: tuple[IndexedSection, ...]) -> HybridSearchIndex:
        """Build an index snapshot."""
        ...


class AnswerGenerator(Protocol):
    """Generate structured claims from retrieved evidence only."""

    def generate(self, question: str, evidence: tuple[RetrievalHit, ...]) -> GeneratedAnswerDraft:
        """Return a draft that must still be grounded by the application."""
        ...


class Retriever(Protocol):
    """Retrieve evidence through a mandatory authorization scope."""

    def retrieve(
        self, question: str, scope: RetrievalScope, *, limit: int
    ) -> tuple[RetrievalHit, ...]:
        """Return relevant allowed evidence."""
        ...
