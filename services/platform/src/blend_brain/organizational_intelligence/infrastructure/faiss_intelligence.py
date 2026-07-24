"""FAISS project similarity and evidence-aware expert ranking."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import faiss
import numpy as np

from blend_brain.organizational_intelligence.domain import (
    ExpertMatch,
    GraphEvidence,
    NodeType,
    ProjectIntelligenceRecord,
    ProjectNotFoundError,
    SimilaritySignal,
    SimilarProject,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from blend_brain.organizational_intelligence.application.ports import IntelligenceIndex

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN.finditer(value)}


def _record_signals(record: ProjectIntelligenceRecord) -> tuple[SimilaritySignal, ...]:
    groups = (
        (NodeType.INDUSTRY, record.industries),
        (NodeType.USE_CASE, record.use_cases),
        (NodeType.CAPABILITY, record.capabilities),
        (NodeType.TECHNOLOGY, record.technologies),
        (NodeType.CLOUD_PLATFORM, record.cloud_platforms),
    )
    return tuple(SimilaritySignal(kind, value) for kind, values in groups for value in values)


@dataclass(slots=True)
class _ExpertAggregate:
    name: str
    best_score: float = 0.0
    project_ids: set[str] = field(default_factory=set)
    signals: dict[tuple[NodeType, str], SimilaritySignal] = field(default_factory=dict)
    evidence: dict[tuple[str, int, str], GraphEvidence] = field(default_factory=dict)


class FaissIntelligenceIndex:
    """Immutable exact-cosine index for project and expert discovery."""

    def __init__(
        self,
        records: tuple[ProjectIntelligenceRecord, ...],
        *,
        minimum_similarity: float,
        minimum_expert_score: float,
    ) -> None:
        self._records = records
        self._minimum_similarity = minimum_similarity
        self._minimum_expert_score = minimum_expert_score
        self._by_project = {record.project_id: index for index, record in enumerate(records)}
        if len(self._by_project) != len(records):
            raise ValueError("Project intelligence records must have unique project IDs")
        self._dimensions = len(records[0].embedding) if records else 0
        if any(len(record.embedding) != self._dimensions for record in records):
            raise ValueError("All Project DNA embeddings must have identical dimensions")
        self._index: faiss.IndexFlatIP | None = None
        if records:
            vectors = np.asarray([record.embedding for record in records], dtype=np.float32)
            if np.any(np.linalg.norm(vectors, axis=1) == 0.0):
                raise ValueError("Project DNA embeddings cannot be zero vectors")
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(self._dimensions)
            index.add(vectors)
            self._index = index

    def similar_projects(self, project_id: str, *, limit: int) -> tuple[SimilarProject, ...]:
        """Return cosine-ranked projects and graph-derived overlap explanations."""
        source_index = self._by_project.get(project_id)
        if source_index is None:
            raise ProjectNotFoundError(
                "Project is not present in the authorized intelligence corpus",
                project_id=project_id,
            )
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        source = self._records[source_index]
        query: NDArray[np.float32] = np.asarray([source.embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        scores, indices = self._search(query, len(self._records))
        source_signals = {(item.kind, item.value.casefold()) for item in _record_signals(source)}
        matches: list[SimilarProject] = []
        for index, score in zip(indices[0], scores[0], strict=True):
            if index < 0 or int(index) == source_index or float(score) < self._minimum_similarity:
                continue
            candidate = self._records[int(index)]
            shared = tuple(
                item
                for item in _record_signals(candidate)
                if (item.kind, item.value.casefold()) in source_signals
            )
            matches.append(
                SimilarProject(
                    project_id=candidate.project_id,
                    display_name=candidate.display_name,
                    score=round(float(score), 4),
                    shared_signals=shared,
                )
            )
            if len(matches) >= limit:
                break
        return tuple(matches)

    def find_experts(
        self,
        query: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[ExpertMatch, ...]:
        """Rank explicit experts through semantically relevant associated projects."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if not self._records:
            return ()
        query_vector = self._query_vector(query_embedding)
        scores, indices = self._search(query_vector, len(self._records))
        query_tokens = _tokens(query)
        experts: dict[str, _ExpertAggregate] = {}
        for index, cosine in zip(indices[0], scores[0], strict=True):
            if index < 0:
                continue
            record = self._records[int(index)]
            signals = _record_signals(record)
            signal_tokens = (
                set().union(*(_tokens(item.value) for item in signals)) if signals else set()
            )
            exact = len(query_tokens & signal_tokens) / len(query_tokens) if query_tokens else 0.0
            semantic = max(0.0, min(1.0, (float(cosine) + 1.0) / 2.0))
            project_score = 0.8 * semantic + 0.2 * exact
            matched = tuple(item for item in signals if _tokens(item.value) & query_tokens)
            for expert in record.experts:
                aggregate = experts.setdefault(expert.expert_id, _ExpertAggregate(expert.name))
                aggregate.best_score = max(aggregate.best_score, project_score)
                aggregate.project_ids.add(record.project_id)
                for signal in matched:
                    aggregate.signals[(signal.kind, signal.value.casefold())] = signal
                for evidence in expert.evidence:
                    aggregate.evidence[
                        (evidence.document_id, evidence.section_sequence, evidence.quote)
                    ] = evidence

        results = [
            ExpertMatch(
                expert_id=expert_id,
                name=aggregate.name,
                score=round(
                    min(
                        0.99,
                        aggregate.best_score + min(0.1, 0.025 * (len(aggregate.project_ids) - 1)),
                    ),
                    4,
                ),
                project_ids=tuple(sorted(aggregate.project_ids)),
                matched_signals=tuple(
                    sorted(aggregate.signals.values(), key=lambda item: (item.kind, item.value))
                ),
                evidence=tuple(aggregate.evidence.values()),
            )
            for expert_id, aggregate in experts.items()
            if aggregate.best_score >= self._minimum_expert_score
        ]
        return tuple(sorted(results, key=lambda item: (-item.score, item.name.casefold()))[:limit])

    def _query_vector(self, embedding: tuple[float, ...]) -> NDArray[np.float32]:
        if len(embedding) != self._dimensions or not all(
            math.isfinite(value) for value in embedding
        ):
            raise ValueError("Expert query embedding dimensions or values are invalid")
        vector: NDArray[np.float32] = np.asarray([embedding], dtype=np.float32)
        if float(np.linalg.norm(vector)) == 0.0:
            raise ValueError("Expert query embedding cannot be a zero vector")
        faiss.normalize_L2(vector)
        return vector

    def _search(
        self, query: NDArray[np.float32], limit: int
    ) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
        if self._index is None:  # pragma: no cover - guarded by caller/source lookup
            empty_scores: NDArray[np.float32] = np.empty((1, 0), dtype=np.float32)
            empty_indices: NDArray[np.int64] = np.empty((1, 0), dtype=np.int64)
            return empty_scores, empty_indices
        return self._index.search(query, limit)


class FaissIntelligenceIndexFactory:
    """Validated factory for consistent Phase 6 read projections."""

    def __init__(
        self,
        *,
        minimum_similarity: float = 0.6,
        minimum_expert_score: float = 0.55,
    ) -> None:
        if not 0.0 <= minimum_similarity <= 1.0:
            raise ValueError("minimum_similarity must be between zero and one")
        if not 0.0 <= minimum_expert_score <= 1.0:
            raise ValueError("minimum_expert_score must be between zero and one")
        self._minimum_similarity = minimum_similarity
        self._minimum_expert_score = minimum_expert_score

    def build(self, records: tuple[ProjectIntelligenceRecord, ...]) -> IntelligenceIndex:
        """Build one immutable exact-cosine intelligence index."""
        return FaissIntelligenceIndex(
            records,
            minimum_similarity=self._minimum_similarity,
            minimum_expert_score=self._minimum_expert_score,
        )
