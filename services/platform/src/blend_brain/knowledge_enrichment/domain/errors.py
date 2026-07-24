"""Stable errors raised by Phase 3 workflows."""

from __future__ import annotations

from typing import Any


class EnrichmentError(Exception):
    """Base error carrying a stable code and safe diagnostic context."""

    code = "enrichment_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class EnrichmentInputTooLargeError(EnrichmentError):
    """Input exceeds a model or persistence resource limit."""

    code = "enrichment_input_too_large"


class ProjectDNAGenerationError(EnrichmentError):
    """Project DNA could not be generated or parsed."""

    code = "project_dna_generation_failed"


class UngroundedProjectDNAError(ProjectDNAGenerationError):
    """Generated Project DNA contains evidence not present in the source."""

    code = "project_dna_ungrounded"


class EmbeddingGenerationError(EnrichmentError):
    """Embedding generation returned an invalid or failed response."""

    code = "embedding_generation_failed"


class PersistenceError(EnrichmentError):
    """The enrichment bundle could not be committed atomically."""

    code = "enrichment_persistence_failed"
