"""Scoped hybrid retrieval with atomic, bounded index caching."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import TYPE_CHECKING

from blend_brain.knowledge_retrieval.domain import (
    InvalidRetrievalRequestError,
    RetrievalHit,
    RetrievalScope,
)

if TYPE_CHECKING:
    from blend_brain.knowledge_retrieval.application.ports import (
        HybridSearchIndex,
        HybridSearchIndexFactory,
        QueryEmbeddingGateway,
        RetrievalCorpusRepository,
    )


class HybridRetrievalService:
    """Retrieve scoped evidence using cached immutable index snapshots.

    Indexes are keyed by an exact authorization-scope fingerprint. This is an
    intentional defense against applying post-search ACL filters, which can leak
    result existence or reduce recall unpredictably.
    """

    def __init__(
        self,
        *,
        corpus_repository: RetrievalCorpusRepository,
        embedding_gateway: QueryEmbeddingGateway,
        index_factory: HybridSearchIndexFactory,
        max_cached_scopes: int = 32,
        max_question_characters: int = 4_000,
    ) -> None:
        if min(max_cached_scopes, max_question_characters) <= 0:
            raise ValueError("Retrieval limits must be greater than zero")
        self._corpus_repository = corpus_repository
        self._embedding_gateway = embedding_gateway
        self._index_factory = index_factory
        self._max_cached_scopes = max_cached_scopes
        self._max_question_characters = max_question_characters
        self._indexes: OrderedDict[str, HybridSearchIndex] = OrderedDict()
        self._lock = RLock()

    def retrieve(
        self,
        question: str,
        scope: RetrievalScope,
        *,
        limit: int,
    ) -> tuple[RetrievalHit, ...]:
        """Embed and search a validated question within the exact allowed scope."""
        normalized = self._validate_question(question)
        if limit <= 0:
            raise InvalidRetrievalRequestError("Retrieval limit must be greater than zero")
        index = self._index_for(scope)
        query_embedding = self._embedding_gateway.embed_query(normalized)
        return index.search(normalized, query_embedding, limit=limit)

    def refresh(self, scope: RetrievalScope) -> int:
        """Atomically replace one scope's snapshot and return its section count."""
        sections = self._corpus_repository.load(scope)
        index = self._index_factory.build(sections)
        self._store(scope.fingerprint, index)
        return len(sections)

    def invalidate(self, scope: RetrievalScope) -> bool:
        """Remove a cached scope after an ingestion/enrichment completion event."""
        with self._lock:
            return self._indexes.pop(scope.fingerprint, None) is not None

    def _index_for(self, scope: RetrievalScope) -> HybridSearchIndex:
        key = scope.fingerprint
        with self._lock:
            cached = self._indexes.get(key)
            if cached is not None:
                self._indexes.move_to_end(key)
                return cached
            sections = self._corpus_repository.load(scope)
            index = self._index_factory.build(sections)
            self._store_locked(key, index)
            return index

    def _store(self, key: str, index: HybridSearchIndex) -> None:
        with self._lock:
            self._store_locked(key, index)

    def _store_locked(self, key: str, index: HybridSearchIndex) -> None:
        self._indexes[key] = index
        self._indexes.move_to_end(key)
        while len(self._indexes) > self._max_cached_scopes:
            self._indexes.popitem(last=False)

    def _validate_question(self, question: str) -> str:
        normalized = question.strip()
        if not normalized:
            raise InvalidRetrievalRequestError("Question cannot be empty")
        if len(normalized) > self._max_question_characters:
            raise InvalidRetrievalRequestError(
                "Question exceeds the configured character limit",
                character_count=len(normalized),
                character_limit=self._max_question_characters,
            )
        return normalized
