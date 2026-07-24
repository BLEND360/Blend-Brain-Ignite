"""Immutable domain models for Phase 6 intelligence capabilities."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty")
    return normalized


class NodeType(StrEnum):
    """Supported evidence-derived graph entity types."""

    PROJECT = "project"
    CLIENT = "client"
    INDUSTRY = "industry"
    ENGAGEMENT_TYPE = "engagement_type"
    USE_CASE = "use_case"
    CAPABILITY = "capability"
    TECHNOLOGY = "technology"
    DATA_SOURCE = "data_source"
    CLOUD_PLATFORM = "cloud_platform"
    OUTCOME = "outcome"
    DIFFERENTIATOR = "differentiator"
    EXPERT = "expert"


class RelationshipType(StrEnum):
    """Allowed project-to-entity relationships."""

    HAS_CLIENT = "has_client"
    IN_INDUSTRY = "in_industry"
    HAS_ENGAGEMENT_TYPE = "has_engagement_type"
    HAS_USE_CASE = "has_use_case"
    HAS_CAPABILITY = "has_capability"
    USES_TECHNOLOGY = "uses_technology"
    USES_DATA_SOURCE = "uses_data_source"
    USES_CLOUD_PLATFORM = "uses_cloud_platform"
    DELIVERED_OUTCOME = "delivered_outcome"
    HAS_DIFFERENTIATOR = "has_differentiator"
    INVOLVED_EXPERT = "involved_expert"


@dataclass(frozen=True, slots=True)
class IntelligenceScope:
    """Explicit project allowlist supplied by a trusted authorization layer."""

    project_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({_required(value, "project_id") for value in self.project_ids}))
        if not normalized:
            raise ValueError("IntelligenceScope requires at least one project_id")
        object.__setattr__(self, "project_ids", normalized)

    @property
    def fingerprint(self) -> str:
        """Return a stable, non-reversible cache key for the exact allowlist."""
        return hashlib.sha256("\0".join(self.project_ids).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GraphEvidence:
    """Exact source evidence retained on a graph relationship."""

    document_id: str
    section_sequence: int
    quote: str


@dataclass(frozen=True, slots=True)
class GraphNode:
    """Canonical entity in the organizational knowledge graph."""

    node_id: str
    node_type: NodeType
    normalized_key: str
    display_name: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Evidence-backed relationship from a project to an entity."""

    edge_id: str
    project_id: str
    dna_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: RelationshipType
    confidence: str
    evidence: tuple[GraphEvidence, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeGraphSnapshot:
    """Atomic deterministic graph projection for one Project DNA version."""

    projection_id: str
    projection_version: int
    project_id: str
    dna_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    projected_at: datetime


@dataclass(frozen=True, slots=True)
class ExpertAssociation:
    """Explicit expert-to-project association with original source evidence."""

    expert_id: str
    name: str
    evidence: tuple[GraphEvidence, ...]


@dataclass(frozen=True, slots=True)
class ProjectIntelligenceRecord:
    """Current project vector and graph attributes used by read projections."""

    project_id: str
    dna_id: str
    display_name: str
    embedding: tuple[float, ...]
    industries: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    cloud_platforms: tuple[str, ...] = ()
    experts: tuple[ExpertAssociation, ...] = ()

    def __post_init__(self) -> None:
        for field in ("project_id", "dna_id", "display_name"):
            _required(getattr(self, field), field)
        if not self.embedding or not all(math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding must contain finite values")


@dataclass(frozen=True, slots=True)
class SimilaritySignal:
    """Human-readable shared graph attribute explaining similarity."""

    kind: NodeType
    value: str


@dataclass(frozen=True, slots=True)
class SimilarProject:
    """Authorized project similarity result with explainability signals."""

    project_id: str
    display_name: str
    score: float
    shared_signals: tuple[SimilaritySignal, ...]


@dataclass(frozen=True, slots=True)
class ExpertMatch:
    """Evidence-ranked expert candidate; identity remains source-derived."""

    expert_id: str
    name: str
    score: float
    project_ids: tuple[str, ...]
    matched_signals: tuple[SimilaritySignal, ...]
    evidence: tuple[GraphEvidence, ...]
