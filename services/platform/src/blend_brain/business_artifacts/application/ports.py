"""Driven ports for Phase 8 infrastructure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from blend_brain.business_artifacts.domain import (
        ArtifactDraft,
        ArtifactExport,
        ArtifactKind,
        ArtifactScope,
        ArtifactSource,
        BusinessArtifact,
        OnePagerBrief,
        ProposalBrief,
    )


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Private location returned by an artifact-storage adapter."""

    storage_location: str
    key: str


class Clock(Protocol):
    """Provide aware UTC time."""

    def now(self) -> datetime:
        """Return the current timestamp."""
        ...


class IdentifierGenerator(Protocol):
    """Generate opaque unique identifiers."""

    def new(self) -> str:
        """Return a new identifier."""
        ...


class BusinessArtifactGenerator(Protocol):
    """Generate typed, grounded artifact drafts."""

    def generate_proposal(
        self, brief: ProposalBrief, sources: tuple[ArtifactSource, ...]
    ) -> ArtifactDraft:
        """Generate a proposal draft."""
        ...

    def generate_one_pager(
        self, brief: OnePagerBrief, sources: tuple[ArtifactSource, ...]
    ) -> ArtifactDraft:
        """Generate a project one-pager draft."""
        ...


class BusinessArtifactRepository(Protocol):
    """Load scoped evidence and persist generated artifact records."""

    def load_project_sources(self, project_ids: tuple[str, ...]) -> tuple[ArtifactSource, ...]:
        """Load current source sections for only the requested projects."""
        ...

    def find_by_request(
        self,
        request_id: str,
        kind: ArtifactKind,
        created_by: str,
        project_ids: tuple[str, ...],
    ) -> BusinessArtifact | None:
        """Return an existing idempotent generation result."""
        ...

    def persist(self, artifact: BusinessArtifact, sources: tuple[ArtifactSource, ...]) -> None:
        """Atomically persist an artifact and its resolved citations."""
        ...

    def get_artifact(
        self, artifact_id: str, kind: ArtifactKind, scope: ArtifactScope
    ) -> BusinessArtifact | None:
        """Load an artifact only when every source project is authorized."""
        ...

    def record_export(self, export: ArtifactExport) -> None:
        """Persist PDF object metadata."""
        ...


class PdfRenderer(Protocol):
    """Render an artifact into a PDF byte stream."""

    def render(self, artifact: BusinessArtifact) -> bytes:
        """Return a complete PDF document."""
        ...


class ArtifactObjectStore(Protocol):
    """Store private artifact exports behind a location-independent port."""

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        """Store bytes privately and return their location."""
        ...

    def delete(self, key: str) -> None:
        """Delete an object during compensating cleanup."""
        ...
