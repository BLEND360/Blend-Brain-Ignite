"""Immutable domain models for grounded business artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty")
    return normalized


class ArtifactKind(StrEnum):
    """Business artifact templates supported by Phase 8."""

    PROPOSAL = "proposal"
    PROJECT_ONE_PAGER = "project_one_pager"


class ArtifactStatus(StrEnum):
    """Generated artifacts remain drafts until a future publishing workflow."""

    DRAFT = "draft"


class ArtifactSourceKind(StrEnum):
    """Trusted provenance class for model context."""

    USER_BRIEF = "user_brief"
    PROJECT_DOCUMENT = "project_document"


class ArtifactPermission(StrEnum):
    """Fine-grained capabilities supplied by a trusted identity layer."""

    GENERATE = "artifact:generate"
    EXPORT = "artifact:export"


@dataclass(frozen=True, slots=True)
class ArtifactActor:
    """Authenticated actor and explicit artifact permissions."""

    actor_id: str
    permissions: frozenset[ArtifactPermission]

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _required(self.actor_id, "actor_id"))


@dataclass(frozen=True, slots=True)
class ArtifactScope:
    """Exact project allowlist supplied by a trusted authorization layer."""

    project_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({_required(value, "project_id") for value in self.project_ids}))
        if not normalized:
            raise ValueError("ArtifactScope requires at least one project_id")
        object.__setattr__(self, "project_ids", normalized)

    def contains_all(self, project_ids: tuple[str, ...]) -> bool:
        """Return whether every requested project is authorized."""
        return set(project_ids).issubset(self.project_ids)


@dataclass(frozen=True, slots=True)
class ArtifactSource:
    """One addressable source made available to the generator."""

    source_id: str
    kind: ArtifactSourceKind
    text: str
    project_id: str | None = None
    document_id: str | None = None
    section_sequence: int | None = None
    filename: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required(self.source_id, "source_id"))
        object.__setattr__(self, "text", _required(self.text, "text"))


@dataclass(frozen=True, slots=True)
class ArtifactCitation:
    """Exact quote from an addressable artifact source."""

    source_id: str
    quote: str
    source_kind: ArtifactSourceKind | None = None
    project_id: str | None = None
    document_id: str | None = None
    section_sequence: int | None = None
    filename: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactStatement:
    """One generated statement with mandatory grounding."""

    text: str
    citations: tuple[ArtifactCitation, ...]


@dataclass(frozen=True, slots=True)
class ArtifactSection:
    """Ordered template section containing grounded statements."""

    key: str
    heading: str
    statements: tuple[ArtifactStatement, ...]


@dataclass(frozen=True, slots=True)
class ProposalBrief:
    """User-supplied opportunity context captured with the proposal."""

    client_name: str
    audience: str
    opportunity: str
    objectives: tuple[str, ...]
    constraints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OnePagerBrief:
    """One-project audience context captured with the one-pager."""

    project_id: str
    audience: str


@dataclass(frozen=True, slots=True)
class ArtifactDraft:
    """Grounded model output before application metadata is attached."""

    title: str
    subtitle: str | None
    sections: tuple[ArtifactSection, ...]
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class ProposalArtifact:
    """Versioned, persisted AI-generated proposal draft."""

    artifact_id: str
    request_id: str
    source_project_ids: tuple[str, ...]
    brief: ProposalBrief
    title: str
    subtitle: str | None
    sections: tuple[ArtifactSection, ...]
    model: str
    prompt_version: str
    status: ArtifactStatus
    content_sha256: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectOnePagerArtifact:
    """Versioned, persisted AI-generated project one-pager draft."""

    artifact_id: str
    request_id: str
    source_project_ids: tuple[str, ...]
    brief: OnePagerBrief
    title: str
    subtitle: str | None
    sections: tuple[ArtifactSection, ...]
    model: str
    prompt_version: str
    status: ArtifactStatus
    content_sha256: str
    created_by: str
    created_at: datetime


type BusinessArtifact = ProposalArtifact | ProjectOnePagerArtifact


@dataclass(frozen=True, slots=True)
class ArtifactExport:
    """Durable metadata for a privately stored PDF export."""

    export_id: str
    artifact_id: str
    artifact_kind: ArtifactKind
    storage_location: str
    object_key: str
    content_type: str
    size_bytes: int
    sha256: str
    created_by: str
    created_at: datetime


def artifact_content_sha256(draft: ArtifactDraft) -> str:
    """Hash canonical generated content for audit and idempotency."""
    payload = {
        "title": draft.title,
        "subtitle": draft.subtitle,
        "sections": [asdict(section) for section in draft.sections],
        "model": draft.model,
        "prompt_version": draft.prompt_version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()
