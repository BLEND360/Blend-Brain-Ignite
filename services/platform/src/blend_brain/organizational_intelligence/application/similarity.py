"""Authorized explainable project similarity workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blend_brain.organizational_intelligence.domain import (
    IntelligenceRequestError,
    SimilarProject,
)

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.application.index_registry import (
        IntelligenceIndexRegistry,
    )
    from blend_brain.organizational_intelligence.domain import IntelligenceScope


class ProjectSimilarityService:
    """Find semantically similar projects within an explicit allowed scope."""

    def __init__(self, registry: IntelligenceIndexRegistry, *, default_limit: int = 6) -> None:
        if default_limit <= 0:
            raise ValueError("default_limit must be greater than zero")
        self._registry = registry
        self._default_limit = default_limit

    def find_similar(
        self,
        project_id: str,
        scope: IntelligenceScope,
        *,
        limit: int | None = None,
    ) -> tuple[SimilarProject, ...]:
        """Return vector-ranked projects with graph-derived shared signals."""
        normalized_id = project_id.strip()
        if not normalized_id:
            raise IntelligenceRequestError("project_id cannot be empty")
        requested_limit = self._default_limit if limit is None else limit
        if requested_limit <= 0:
            raise IntelligenceRequestError("Similarity limit must be greater than zero")
        return self._registry.get(scope).similar_projects(normalized_id, limit=requested_limit)
