"""Immutable Phase 3 knowledge-enrichment domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from blend_brain.document_ingestion.domain import ExtractedDocument


class ClaimConfidence(StrEnum):
    """Evidence-based confidence assigned to a Project DNA claim."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmbeddingTargetType(StrEnum):
    """Content units embedded during Phase 3."""

    DOCUMENT_SECTION = "document_section"
    PROJECT_DNA = "project_dna"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Exact evidence excerpt tied to an extracted section."""

    section_sequence: int
    quote: str


@dataclass(frozen=True, slots=True)
class GroundedClaim:
    """One semantic fact with explicit source evidence."""

    value: str
    confidence: ClaimConfidence
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class DocumentProfile:
    """Deterministic technical and descriptive metadata for one document version."""

    document_id: str
    source_id: str
    filename: str
    document_format: str
    sha256: str
    size_bytes: int
    title: str | None
    author: str | None
    subject: str | None
    created_at: datetime | None
    modified_at: datetime | None
    section_count: int
    character_count: int
    word_count: int


@dataclass(frozen=True, slots=True)
class ProjectDNA:
    """Versioned organizational description grounded in one document."""

    dna_id: str
    project_id: str
    document_id: str
    version: int
    project_name: GroundedClaim | None
    client_name: GroundedClaim | None
    industry: GroundedClaim | None
    engagement_type: GroundedClaim | None
    summary: GroundedClaim | None
    business_challenges: tuple[GroundedClaim, ...]
    use_cases: tuple[GroundedClaim, ...]
    capabilities: tuple[GroundedClaim, ...]
    technologies: tuple[GroundedClaim, ...]
    data_sources: tuple[GroundedClaim, ...]
    cloud_platforms: tuple[GroundedClaim, ...]
    outcomes: tuple[GroundedClaim, ...]
    differentiators: tuple[GroundedClaim, ...]
    experts: tuple[GroundedClaim, ...]
    model: str
    prompt_version: str
    generated_at: datetime

    def all_claims(self) -> tuple[GroundedClaim, ...]:
        """Return every scalar and collection claim in stable field order."""
        scalar = tuple(
            claim
            for claim in (
                self.project_name,
                self.client_name,
                self.industry,
                self.engagement_type,
                self.summary,
            )
            if claim is not None
        )
        return scalar + (
            self.business_challenges
            + self.use_cases
            + self.capabilities
            + self.technologies
            + self.data_sources
            + self.cloud_platforms
            + self.outcomes
            + self.differentiators
            + self.experts
        )

    def embedding_text(self) -> str:
        """Create deterministic semantic text for project-level similarity."""
        return "\n".join(claim.value for claim in self.all_claims())


@dataclass(frozen=True, slots=True)
class EmbeddingTarget:
    """Stable content unit awaiting embedding generation."""

    embedding_id: str
    project_id: str
    document_id: str
    target_type: EmbeddingTargetType
    target_id: str
    section_sequence: int | None
    content_sha256: str
    text: str


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    """Validated model vector for a stable content target."""

    embedding_id: str
    project_id: str
    document_id: str
    target_type: EmbeddingTargetType
    target_id: str
    section_sequence: int | None
    content_sha256: str
    model: str
    dimensions: int
    vector: tuple[float, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EnrichmentBundle:
    """Atomic persistence unit for a completed Phase 3 run."""

    run_id: str
    project_id: str
    document: ExtractedDocument
    profile: DocumentProfile
    project_dna: ProjectDNA
    embeddings: tuple[EmbeddingRecord, ...]
    completed_at: datetime
