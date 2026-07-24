"""Immutable domain models for scoped retrieval and grounded answers."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty")
    return normalized


class ConfidenceBand(StrEnum):
    """User-facing interpretation of a calibrated heuristic score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    """Explicit project allowlist established by the authorization layer."""

    project_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({_required(value, "project_id") for value in self.project_ids}))
        if not normalized:
            raise ValueError("RetrievalScope requires at least one project_id")
        object.__setattr__(self, "project_ids", normalized)

    @property
    def fingerprint(self) -> str:
        """Return a non-reversible stable cache key for this exact allowlist."""
        return hashlib.sha256("\0".join(self.project_ids).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class IndexedSection:
    """One source section and its durable semantic vector."""

    section_id: str
    project_id: str
    document_id: str
    filename: str
    sequence: int
    kind: str
    text: str
    embedding: tuple[float, ...]
    page_number: int | None = None
    slide_number: int | None = None
    heading: str | None = None

    def __post_init__(self) -> None:
        for field in ("section_id", "project_id", "document_id", "filename", "kind", "text"):
            _required(getattr(self, field), field)
        if self.sequence < 1:
            raise ValueError("sequence must be greater than zero")
        if not self.embedding or not all(math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding must contain finite values")


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """A fused result with auditable component scores and ranks."""

    source_id: str
    section: IndexedSection
    fusion_score: float
    dense_score: float | None
    lexical_score: float | None
    dense_rank: int | None
    lexical_rank: int | None


@dataclass(frozen=True, slots=True)
class GeneratedCitationDraft:
    """Model-proposed citation awaiting deterministic validation."""

    source_id: str
    quote: str


@dataclass(frozen=True, slots=True)
class GeneratedClaimDraft:
    """Model-proposed claim and its proposed evidence."""

    text: str
    citations: tuple[GeneratedCitationDraft, ...]


@dataclass(frozen=True, slots=True)
class GeneratedAnswerDraft:
    """Structured model output before the trust boundary is crossed."""

    answerable: bool
    claims: tuple[GeneratedClaimDraft, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerCitation:
    """Validated, source-addressable evidence returned to a caller."""

    citation_id: str
    project_id: str
    document_id: str
    filename: str
    section_sequence: int
    quote: str
    page_number: int | None = None
    slide_number: int | None = None
    heading: str | None = None


@dataclass(frozen=True, slots=True)
class GroundedAnswerClaim:
    """One answer statement whose citation identifiers are all validated."""

    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConfidenceBreakdown:
    """Transparent normalized inputs to the confidence calculation."""

    retrieval_strength: float
    citation_coverage: float
    source_diversity: float


@dataclass(frozen=True, slots=True)
class AnswerConfidence:
    """Application-computed confidence; never a model self-assessment."""

    score: float
    band: ConfidenceBand
    breakdown: ConfidenceBreakdown


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Final Phase 4 result with no unsupported free-form answer channel."""

    question: str
    answerable: bool
    answer: str | None
    claims: tuple[GroundedAnswerClaim, ...]
    citations: tuple[AnswerCitation, ...]
    confidence: AnswerConfidence
    reason: str | None = None
