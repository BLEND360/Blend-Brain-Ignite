"""FAISS cosine search, BM25 lexical search, and reciprocal-rank fusion."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import faiss
import numpy as np

from blend_brain.knowledge_retrieval.domain import IndexedSection, RetrievalHit

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from blend_brain.knowledge_retrieval.application.ports import HybridSearchIndex

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN.finditer(value))


class _BM25Index:
    """Small immutable Okapi BM25 implementation with deterministic ranking."""

    def __init__(self, documents: tuple[str, ...], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._term_frequencies = tuple(Counter(_tokens(document)) for document in documents)
        self._lengths = tuple(sum(counts.values()) for counts in self._term_frequencies)
        self._average_length = sum(self._lengths) / len(documents) if documents else 0.0
        document_frequency: Counter[str] = Counter()
        for counts in self._term_frequencies:
            document_frequency.update(counts.keys())
        size = len(documents)
        self._idf = {
            term: math.log(1.0 + (size - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: str) -> tuple[float, ...]:
        """Score every document; repeated query terms do not multiply relevance."""
        terms = set(_tokens(query))
        results: list[float] = []
        for counts, length in zip(self._term_frequencies, self._lengths, strict=True):
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency == 0:
                    continue
                length_ratio = length / self._average_length if self._average_length else 0.0
                denominator = frequency + self._k1 * (1.0 - self._b + self._b * length_ratio)
                score += self._idf[term] * frequency * (self._k1 + 1.0) / denominator
            results.append(score)
        return tuple(results)


@dataclass(frozen=True, slots=True)
class _Candidate:
    dense_score: float | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fusion_score: float = 0.0


class FaissHybridSearchIndex:
    """Immutable exact-cosine FAISS index fused with an immutable BM25 index."""

    def __init__(
        self,
        sections: tuple[IndexedSection, ...],
        *,
        rrf_k: int,
        dense_weight: float,
        lexical_weight: float,
        candidate_multiplier: int,
    ) -> None:
        self._sections = sections
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight
        self._lexical_weight = lexical_weight
        self._candidate_multiplier = candidate_multiplier
        self._bm25 = _BM25Index(tuple(section.text for section in sections))
        self._dimensions = len(sections[0].embedding) if sections else 0
        if any(len(section.embedding) != self._dimensions for section in sections):
            raise ValueError("All corpus embeddings must have identical dimensions")
        self._dense_index: faiss.IndexFlatIP | None = None
        if sections:
            vectors = np.asarray([section.embedding for section in sections], dtype=np.float32)
            if np.any(np.linalg.norm(vectors, axis=1) == 0.0):
                raise ValueError("Corpus embeddings cannot be zero vectors")
            faiss.normalize_L2(vectors)
            dense_index = faiss.IndexFlatIP(self._dimensions)
            dense_index.add(vectors)
            self._dense_index = dense_index

    def search(
        self,
        query: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[RetrievalHit, ...]:
        """Search both modalities and fuse ranks without mixing raw score scales."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if not self._sections:
            return ()
        if len(query_embedding) != self._dimensions or not all(
            math.isfinite(value) for value in query_embedding
        ):
            raise ValueError("Query embedding dimensions or values are invalid")
        query_vector: NDArray[np.float32] = np.asarray([query_embedding], dtype=np.float32)
        if float(np.linalg.norm(query_vector)) == 0.0:
            raise ValueError("Query embedding cannot be a zero vector")
        faiss.normalize_L2(query_vector)
        candidate_limit = min(len(self._sections), max(limit * self._candidate_multiplier, 20))
        if self._dense_index is None:  # pragma: no cover - guaranteed by non-empty corpus
            raise RuntimeError("Dense index is unavailable")
        dense_scores, dense_indices = self._dense_index.search(query_vector, candidate_limit)
        candidates: dict[int, _Candidate] = {}
        for rank, (index, score) in enumerate(
            zip(dense_indices[0], dense_scores[0], strict=True), start=1
        ):
            if index < 0:
                continue
            candidates[int(index)] = _Candidate(
                dense_score=float(score),
                dense_rank=rank,
                fusion_score=self._dense_weight / (self._rrf_k + rank),
            )

        lexical_scores = self._bm25.scores(query)
        lexical_order = sorted(
            (index for index, score in enumerate(lexical_scores) if score > 0.0),
            key=lambda index: (-lexical_scores[index], self._sections[index].section_id),
        )[:candidate_limit]
        for rank, index in enumerate(lexical_order, start=1):
            current = candidates.get(index, _Candidate())
            candidates[index] = _Candidate(
                dense_score=current.dense_score,
                lexical_score=lexical_scores[index],
                dense_rank=current.dense_rank,
                lexical_rank=rank,
                fusion_score=current.fusion_score + self._lexical_weight / (self._rrf_k + rank),
            )

        ordered = sorted(
            candidates.items(),
            key=lambda item: (-item[1].fusion_score, self._sections[item[0]].section_id),
        )[:limit]
        return tuple(
            RetrievalHit(
                source_id=f"S{rank}",
                section=self._sections[index],
                fusion_score=candidate.fusion_score,
                dense_score=candidate.dense_score,
                lexical_score=candidate.lexical_score,
                dense_rank=candidate.dense_rank,
                lexical_rank=candidate.lexical_rank,
            )
            for rank, (index, candidate) in enumerate(ordered, start=1)
        )


class FaissHybridSearchIndexFactory:
    """Validated factory for consistently configured hybrid snapshots."""

    def __init__(
        self,
        *,
        rrf_k: int = 60,
        dense_weight: float = 0.6,
        lexical_weight: float = 0.4,
        candidate_multiplier: int = 4,
    ) -> None:
        if min(rrf_k, candidate_multiplier) <= 0:
            raise ValueError("RRF limits must be greater than zero")
        if dense_weight < 0 or lexical_weight < 0 or dense_weight + lexical_weight <= 0:
            raise ValueError("At least one non-negative retrieval weight is required")
        total = dense_weight + lexical_weight
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight / total
        self._lexical_weight = lexical_weight / total
        self._candidate_multiplier = candidate_multiplier

    def build(self, sections: tuple[IndexedSection, ...]) -> HybridSearchIndex:
        """Build an exact-cosine index suitable for the Phase 4 corpus scale."""
        return FaissHybridSearchIndex(
            sections,
            rrf_k=self._rrf_k,
            dense_weight=self._dense_weight,
            lexical_weight=self._lexical_weight,
            candidate_multiplier=self._candidate_multiplier,
        )
