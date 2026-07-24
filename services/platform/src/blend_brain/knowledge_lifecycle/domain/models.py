"""Immutable models for knowledge-gap and approval governance."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty")
    return normalized


class KnowledgePermission(StrEnum):
    """Fine-grained permissions supplied by a trusted identity layer."""

    CAPTURE = "knowledge:capture"
    REVIEW = "knowledge:review"


class GapField(StrEnum):
    """Project DNA fields that can be assessed and supplemented."""

    PROJECT_NAME = "project_name"
    CLIENT_NAME = "client_name"
    INDUSTRY = "industry"
    ENGAGEMENT_TYPE = "engagement_type"
    SUMMARY = "summary"
    BUSINESS_CHALLENGES = "business_challenges"
    USE_CASES = "use_cases"
    CAPABILITIES = "capabilities"
    TECHNOLOGIES = "technologies"
    DATA_SOURCES = "data_sources"
    CLOUD_PLATFORMS = "cloud_platforms"
    OUTCOMES = "outcomes"
    DIFFERENTIATORS = "differentiators"
    EXPERTS = "experts"


class GapKind(StrEnum):
    """Deterministic reasons a field needs knowledge."""

    MISSING = "missing"
    LOW_CONFIDENCE = "low_confidence"


class GapSeverity(StrEnum):
    """Business priority assigned by the detection policy."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapStatus(StrEnum):
    """Lifecycle state of a detected gap."""

    OPEN = "open"
    RESOLVED = "resolved"


class SubmissionStatus(StrEnum):
    """Allowed knowledge-submission states."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApprovalAction(StrEnum):
    """Immutable workflow audit actions."""

    CAPTURED = "captured"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class KnowledgeActor:
    """Authenticated actor and permissions from a trusted identity layer."""

    actor_id: str
    permissions: frozenset[KnowledgePermission]

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _required(self.actor_id, "actor_id"))


@dataclass(frozen=True, slots=True)
class KnowledgeScope:
    """Exact project allowlist supplied by an authorization layer."""

    project_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({_required(item, "project_id") for item in self.project_ids}))
        if not normalized:
            raise ValueError("KnowledgeScope requires at least one project_id")
        object.__setattr__(self, "project_ids", normalized)

    def includes(self, project_id: str) -> bool:
        """Return whether the normalized project identifier is authorized."""
        return project_id.strip() in self.project_ids


@dataclass(frozen=True, slots=True)
class KnowledgeGap:
    """One deterministic deficiency in a Project DNA version."""

    gap_id: str
    project_id: str
    dna_id: str
    field: GapField
    kind: GapKind
    severity: GapSeverity
    explanation: str
    observed_values: tuple[str, ...]
    status: GapStatus
    detected_at: datetime


@dataclass(frozen=True, slots=True)
class GapAssessment:
    """Complete replaceable gap assessment for one Project DNA version."""

    assessment_id: str
    policy_version: int
    project_id: str
    dna_id: str
    gaps: tuple[KnowledgeGap, ...]
    detected_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeSubmission:
    """Human-supplied proposed knowledge under explicit governance."""

    submission_id: str
    project_id: str
    gap_id: str | None
    field: GapField
    proposed_value: str
    rationale: str | None
    source_reference: str | None
    submitter_id: str
    status: SubmissionStatus
    version: int
    created_at: datetime
    updated_at: datetime

    def transition(self, status: SubmissionStatus, *, at: datetime) -> KnowledgeSubmission:
        """Return the next immutable optimistic-lock version."""
        return replace(self, status=status, version=self.version + 1, updated_at=at)


@dataclass(frozen=True, slots=True)
class ApprovalEvent:
    """Append-only audit event for one workflow action."""

    event_id: str
    submission_id: str
    project_id: str
    action: ApprovalAction
    actor_id: str
    from_status: SubmissionStatus | None
    to_status: SubmissionStatus
    reason: str | None
    submission_version: int
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovedKnowledge:
    """Governed fact produced only by an atomic approval transition."""

    fact_id: str
    submission_id: str
    project_id: str
    field: GapField
    value: str
    source_reference: str | None
    approved_by: str
    approved_at: datetime
