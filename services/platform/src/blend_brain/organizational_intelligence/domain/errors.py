"""Stable Phase 6 organizational intelligence errors."""

from __future__ import annotations

from typing import Any


class IntelligenceError(Exception):
    """Base error with a stable code and safe diagnostic context."""

    code = "organizational_intelligence_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class IntelligenceRequestError(IntelligenceError):
    """A scope, query, or result limit is invalid."""

    code = "invalid_intelligence_request"


class ProjectNotFoundError(IntelligenceError):
    """The requested project is absent from the authorized corpus."""

    code = "intelligence_project_not_found"


class IntelligenceCorpusError(IntelligenceError):
    """The project intelligence corpus could not be loaded."""

    code = "intelligence_corpus_load_failed"


class GraphPersistenceError(IntelligenceError):
    """A graph snapshot could not be committed atomically."""

    code = "knowledge_graph_persistence_failed"


class IntelligenceEmbeddingError(IntelligenceError):
    """An Expert Finder query embedding could not be generated."""

    code = "intelligence_embedding_failed"
