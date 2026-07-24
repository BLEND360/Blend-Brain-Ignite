"""Semantic and evidence-backed Expert Finder workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blend_brain.organizational_intelligence.domain import (
    ExpertMatch,
    IntelligenceRequestError,
)

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.application.index_registry import (
        IntelligenceIndexRegistry,
    )
    from blend_brain.organizational_intelligence.application.ports import (
        IntelligenceQueryEmbeddingGateway,
    )
    from blend_brain.organizational_intelligence.domain import IntelligenceScope


class ExpertFinderService:
    """Find source-named experts through projects relevant to a capability query."""

    def __init__(
        self,
        registry: IntelligenceIndexRegistry,
        embedding_gateway: IntelligenceQueryEmbeddingGateway,
        *,
        default_limit: int = 8,
        max_query_characters: int = 2_000,
    ) -> None:
        if min(default_limit, max_query_characters) <= 0:
            raise ValueError("Expert Finder limits must be greater than zero")
        self._registry = registry
        self._embedding_gateway = embedding_gateway
        self._default_limit = default_limit
        self._max_query_characters = max_query_characters

    def find(
        self,
        query: str,
        scope: IntelligenceScope,
        *,
        limit: int | None = None,
    ) -> tuple[ExpertMatch, ...]:
        """Return ranked candidates with project and source evidence."""
        normalized = query.strip()
        if not normalized:
            raise IntelligenceRequestError("Expert Finder query cannot be empty")
        if len(normalized) > self._max_query_characters:
            raise IntelligenceRequestError(
                "Expert Finder query exceeds the character limit",
                character_count=len(normalized),
                character_limit=self._max_query_characters,
            )
        requested_limit = self._default_limit if limit is None else limit
        if requested_limit <= 0:
            raise IntelligenceRequestError("Expert Finder limit must be greater than zero")
        vector = self._embedding_gateway.embed_query(normalized)
        return self._registry.get(scope).find_experts(normalized, vector, limit=requested_limit)
