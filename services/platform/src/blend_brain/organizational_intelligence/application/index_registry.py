"""Bounded cache of immutable authorized intelligence indexes."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.application.ports import (
        IntelligenceCorpusRepository,
        IntelligenceIndex,
        IntelligenceIndexFactory,
    )
    from blend_brain.organizational_intelligence.domain import IntelligenceScope


class IntelligenceIndexRegistry:
    """Build and cache indexes by the exact authorization-scope fingerprint."""

    def __init__(
        self,
        repository: IntelligenceCorpusRepository,
        index_factory: IntelligenceIndexFactory,
        *,
        max_cached_scopes: int = 32,
    ) -> None:
        if max_cached_scopes <= 0:
            raise ValueError("max_cached_scopes must be greater than zero")
        self._repository = repository
        self._index_factory = index_factory
        self._max_cached_scopes = max_cached_scopes
        self._indexes: OrderedDict[str, IntelligenceIndex] = OrderedDict()
        self._lock = RLock()

    def get(self, scope: IntelligenceScope) -> IntelligenceIndex:
        """Return the immutable index for an exact scope, building it if absent."""
        key = scope.fingerprint
        with self._lock:
            cached = self._indexes.get(key)
            if cached is not None:
                self._indexes.move_to_end(key)
                return cached
            index = self._index_factory.build(self._repository.load(scope))
            self._store_locked(key, index)
            return index

    def refresh(self, scope: IntelligenceScope) -> int:
        """Atomically replace a scope index and return the project count."""
        records = self._repository.load(scope)
        index = self._index_factory.build(records)
        with self._lock:
            self._store_locked(scope.fingerprint, index)
        return len(records)

    def invalidate(self, scope: IntelligenceScope) -> bool:
        """Remove a snapshot after graph or enrichment updates."""
        with self._lock:
            return self._indexes.pop(scope.fingerprint, None) is not None

    def _store_locked(self, key: str, index: IntelligenceIndex) -> None:
        self._indexes[key] = index
        self._indexes.move_to_end(key)
        while len(self._indexes) > self._max_cached_scopes:
            self._indexes.popitem(last=False)
