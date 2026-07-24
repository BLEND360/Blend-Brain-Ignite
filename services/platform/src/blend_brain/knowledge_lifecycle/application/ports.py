"""Driven ports for Phase 7 infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from blend_brain.knowledge_lifecycle.domain import (
        ApprovalEvent,
        ApprovedKnowledge,
        GapAssessment,
        KnowledgeGap,
        KnowledgeSubmission,
        SubmissionStatus,
    )


class Clock(Protocol):
    """Provide an aware current timestamp."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...


class IdentifierGenerator(Protocol):
    """Generate opaque unique identifiers."""

    def new(self) -> str:
        """Return a new identifier."""
        ...


class KnowledgeLifecycleRepository(Protocol):
    """Persist gap assessments and governed knowledge transactions."""

    def replace_assessment(self, assessment: GapAssessment) -> None:
        """Atomically replace gaps for one DNA assessment."""
        ...

    def get_gap(self, gap_id: str, project_id: str) -> KnowledgeGap | None:
        """Load a gap only when it belongs to the requested project."""
        ...

    def create_submission(self, submission: KnowledgeSubmission, event: ApprovalEvent) -> None:
        """Atomically create a draft and its first audit event."""
        ...

    def get_submission(self, submission_id: str, project_id: str) -> KnowledgeSubmission | None:
        """Load a submission only when it belongs to the requested project."""
        ...

    def transition(
        self,
        submission: KnowledgeSubmission,
        event: ApprovalEvent,
        *,
        expected_version: int,
        expected_status: SubmissionStatus,
        fact: ApprovedKnowledge | None = None,
    ) -> None:
        """Atomically compare-and-set state, append audit, and optionally create a fact."""
        ...
