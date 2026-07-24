"""Typed Phase 7 test doubles."""

from __future__ import annotations

from datetime import UTC, datetime

from blend_brain.knowledge_lifecycle.domain import (
    ApprovalEvent,
    ApprovedKnowledge,
    GapAssessment,
    KnowledgeGap,
    KnowledgeSubmission,
    KnowledgeWorkflowConflictError,
    SubmissionStatus,
)

NOW = datetime(2026, 7, 24, 15, 0, tzinfo=UTC)


class FixedClock:
    """Return a deterministic aware timestamp."""

    def now(self) -> datetime:
        """Return test time."""
        return NOW


class SequenceIdentifiers:
    """Generate readable deterministic IDs."""

    def __init__(self) -> None:
        self.count = 0

    def new(self) -> str:
        """Return the next ID."""
        self.count += 1
        return f"generated-{self.count}"


class MemoryRepository:
    """In-memory contract fake preserving optimistic transition behavior."""

    def __init__(self) -> None:
        self.assessments: list[GapAssessment] = []
        self.gaps: dict[tuple[str, str], KnowledgeGap] = {}
        self.submissions: dict[tuple[str, str], KnowledgeSubmission] = {}
        self.events: list[ApprovalEvent] = []
        self.facts: list[ApprovedKnowledge] = []

    def replace_assessment(self, assessment: GapAssessment) -> None:
        """Record assessment and its gaps."""
        self.assessments.append(assessment)
        for gap in assessment.gaps:
            self.gaps[(gap.gap_id, gap.project_id)] = gap

    def get_gap(self, gap_id: str, project_id: str) -> KnowledgeGap | None:
        """Return a scoped gap."""
        return self.gaps.get((gap_id, project_id))

    def create_submission(self, submission: KnowledgeSubmission, event: ApprovalEvent) -> None:
        """Store a submission and event."""
        self.submissions[(submission.submission_id, submission.project_id)] = submission
        self.events.append(event)

    def get_submission(self, submission_id: str, project_id: str) -> KnowledgeSubmission | None:
        """Return a scoped submission."""
        return self.submissions.get((submission_id, project_id))

    def transition(
        self,
        submission: KnowledgeSubmission,
        event: ApprovalEvent,
        *,
        expected_version: int,
        expected_status: SubmissionStatus,
        fact: ApprovedKnowledge | None = None,
    ) -> None:
        """Apply an optimistic state transition."""
        key = (submission.submission_id, submission.project_id)
        current = self.submissions[key]
        if current.version != expected_version or current.status is not expected_status:
            raise KnowledgeWorkflowConflictError("stale")
        self.submissions[key] = submission
        self.events.append(event)
        if fact:
            self.facts.append(fact)
