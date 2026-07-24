"""Knowledge capture and human approval use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blend_brain.knowledge_lifecycle.domain import (
    ApprovalAction,
    ApprovalEvent,
    ApprovedKnowledge,
    GapField,
    GapStatus,
    KnowledgeActor,
    KnowledgeAuthorizationError,
    KnowledgeNotFoundError,
    KnowledgePermission,
    KnowledgeRequestError,
    KnowledgeScope,
    KnowledgeSubmission,
    KnowledgeWorkflowConflictError,
    SubmissionStatus,
)

if TYPE_CHECKING:
    from .ports import Clock, IdentifierGenerator, KnowledgeLifecycleRepository


@dataclass(frozen=True, slots=True)
class CaptureKnowledgeCommand:
    """Validated input boundary for a new human contribution."""

    project_id: str
    field: GapField
    proposed_value: str
    gap_id: str | None = None
    rationale: str | None = None
    source_reference: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureLimits:
    """Bound resource consumption and unsafe oversized submissions."""

    max_value_characters: int = 20_000
    max_rationale_characters: int = 4_000
    max_source_reference_characters: int = 4_000

    def __post_init__(self) -> None:
        if (
            min(
                self.max_value_characters,
                self.max_rationale_characters,
                self.max_source_reference_characters,
            )
            <= 0
        ):
            raise ValueError("Capture limits must be greater than zero")


@dataclass(frozen=True, slots=True)
class ApprovalOutcome:
    """Approved submission and the governed fact committed with it."""

    submission: KnowledgeSubmission
    fact: ApprovedKnowledge


class _WorkflowBase:
    def __init__(
        self,
        repository: KnowledgeLifecycleRepository,
        clock: Clock,
        identifiers: IdentifierGenerator,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers

    @staticmethod
    def _authorize(
        actor: KnowledgeActor,
        scope: KnowledgeScope,
        project_id: str,
        permission: KnowledgePermission,
    ) -> str:
        normalized = project_id.strip()
        if not normalized or not scope.includes(normalized) or permission not in actor.permissions:
            raise KnowledgeAuthorizationError("Actor is not authorized for this project operation")
        return normalized

    def _load(
        self,
        submission_id: str,
        project_id: str,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
        permission: KnowledgePermission,
    ) -> KnowledgeSubmission:
        normalized_project = self._authorize(actor, scope, project_id, permission)
        normalized_id = submission_id.strip()
        if not normalized_id:
            raise KnowledgeRequestError("submission_id cannot be empty")
        submission = self._repository.get_submission(normalized_id, normalized_project)
        if submission is None:
            raise KnowledgeNotFoundError("Knowledge submission was not found in the project scope")
        return submission

    def _event(
        self,
        submission: KnowledgeSubmission,
        action: ApprovalAction,
        actor_id: str,
        previous: SubmissionStatus | None,
        reason: str | None,
    ) -> ApprovalEvent:
        return ApprovalEvent(
            event_id=self._identifiers.new(),
            submission_id=submission.submission_id,
            project_id=submission.project_id,
            action=action,
            actor_id=actor_id,
            from_status=previous,
            to_status=submission.status,
            reason=reason,
            submission_version=submission.version,
            occurred_at=submission.updated_at,
        )


class KnowledgeCaptureService(_WorkflowBase):
    """Capture, submit, or withdraw knowledge owned by the contributor."""

    def __init__(
        self,
        repository: KnowledgeLifecycleRepository,
        clock: Clock,
        identifiers: IdentifierGenerator,
        limits: CaptureLimits | None = None,
    ) -> None:
        super().__init__(repository, clock, identifiers)
        self._limits = limits or CaptureLimits()

    def capture(
        self,
        command: CaptureKnowledgeCommand,
        *,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
    ) -> KnowledgeSubmission:
        """Persist a private draft with its immutable capture event."""
        project_id = self._authorize(actor, scope, command.project_id, KnowledgePermission.CAPTURE)
        value = self._bounded(
            command.proposed_value,
            "proposed_value",
            self._limits.max_value_characters,
        )
        rationale = self._optional_bounded(
            command.rationale, "rationale", self._limits.max_rationale_characters
        )
        source = self._optional_bounded(
            command.source_reference,
            "source_reference",
            self._limits.max_source_reference_characters,
        )
        gap_id = command.gap_id.strip() if command.gap_id else None
        if gap_id:
            gap = self._repository.get_gap(gap_id, project_id)
            if gap is None:
                raise KnowledgeNotFoundError("Knowledge gap was not found in the project scope")
            if gap.field is not command.field:
                raise KnowledgeRequestError("Submission field does not match the linked gap")
            if gap.status is not GapStatus.OPEN:
                raise KnowledgeWorkflowConflictError(
                    "Resolved knowledge gaps cannot accept submissions"
                )
        now = self._clock.now()
        submission = KnowledgeSubmission(
            submission_id=self._identifiers.new(),
            project_id=project_id,
            gap_id=gap_id,
            field=command.field,
            proposed_value=value,
            rationale=rationale,
            source_reference=source,
            submitter_id=actor.actor_id,
            status=SubmissionStatus.DRAFT,
            version=0,
            created_at=now,
            updated_at=now,
        )
        self._repository.create_submission(
            submission,
            self._event(submission, ApprovalAction.CAPTURED, actor.actor_id, None, None),
        )
        return submission

    def submit(
        self,
        submission_id: str,
        project_id: str,
        *,
        expected_version: int,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
    ) -> KnowledgeSubmission:
        """Submit the contributor's current draft for independent review."""
        current = self._load(submission_id, project_id, actor, scope, KnowledgePermission.CAPTURE)
        self._require_owner_and_version(current, actor, expected_version)
        if current.status is not SubmissionStatus.DRAFT:
            raise KnowledgeWorkflowConflictError("Only draft knowledge can be submitted")
        updated = current.transition(SubmissionStatus.SUBMITTED, at=self._clock.now())
        self._repository.transition(
            updated,
            self._event(
                updated,
                ApprovalAction.SUBMITTED,
                actor.actor_id,
                current.status,
                None,
            ),
            expected_version=expected_version,
            expected_status=current.status,
        )
        return updated

    def withdraw(
        self,
        submission_id: str,
        project_id: str,
        *,
        expected_version: int,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
        reason: str | None = None,
    ) -> KnowledgeSubmission:
        """Withdraw the contributor's draft or pending submission."""
        current = self._load(submission_id, project_id, actor, scope, KnowledgePermission.CAPTURE)
        self._require_owner_and_version(current, actor, expected_version)
        if current.status not in {SubmissionStatus.DRAFT, SubmissionStatus.SUBMITTED}:
            raise KnowledgeWorkflowConflictError(
                "Only draft or submitted knowledge can be withdrawn"
            )
        normalized_reason = self._optional_bounded(
            reason, "reason", self._limits.max_rationale_characters
        )
        updated = current.transition(SubmissionStatus.WITHDRAWN, at=self._clock.now())
        self._repository.transition(
            updated,
            self._event(
                updated,
                ApprovalAction.WITHDRAWN,
                actor.actor_id,
                current.status,
                normalized_reason,
            ),
            expected_version=expected_version,
            expected_status=current.status,
        )
        return updated

    @staticmethod
    def _require_owner_and_version(
        submission: KnowledgeSubmission, actor: KnowledgeActor, expected_version: int
    ) -> None:
        if submission.submitter_id != actor.actor_id:
            raise KnowledgeAuthorizationError("Only the submitter can change this contribution")
        if expected_version < 0 or submission.version != expected_version:
            raise KnowledgeWorkflowConflictError("Knowledge submission version is stale")

    @staticmethod
    def _bounded(value: str, field: str, limit: int) -> str:
        normalized = value.strip()
        if not normalized:
            raise KnowledgeRequestError(f"{field} cannot be empty")
        if len(normalized) > limit:
            raise KnowledgeRequestError(f"{field} exceeds the configured character limit")
        return normalized

    @classmethod
    def _optional_bounded(cls, value: str | None, field: str, limit: int) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return cls._bounded(normalized, field, limit) if normalized else None


class KnowledgeApprovalService(_WorkflowBase):
    """Independently approve or reject submitted knowledge."""

    def __init__(
        self,
        repository: KnowledgeLifecycleRepository,
        clock: Clock,
        identifiers: IdentifierGenerator,
        *,
        max_reason_characters: int = 4_000,
    ) -> None:
        super().__init__(repository, clock, identifiers)
        if max_reason_characters <= 0:
            raise ValueError("max_reason_characters must be greater than zero")
        self._max_reason_characters = max_reason_characters

    def approve(
        self,
        submission_id: str,
        project_id: str,
        *,
        expected_version: int,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
        reason: str | None = None,
    ) -> ApprovalOutcome:
        """Atomically approve a submission and create its governed fact."""
        current = self._reviewable(submission_id, project_id, expected_version, actor, scope)
        now = self._clock.now()
        updated = current.transition(SubmissionStatus.APPROVED, at=now)
        normalized_reason = self._reason(reason, required=False)
        fact = ApprovedKnowledge(
            fact_id=self._identifiers.new(),
            submission_id=current.submission_id,
            project_id=current.project_id,
            field=current.field,
            value=current.proposed_value,
            source_reference=current.source_reference,
            approved_by=actor.actor_id,
            approved_at=now,
        )
        self._repository.transition(
            updated,
            self._event(
                updated,
                ApprovalAction.APPROVED,
                actor.actor_id,
                current.status,
                normalized_reason,
            ),
            expected_version=expected_version,
            expected_status=current.status,
            fact=fact,
        )
        return ApprovalOutcome(updated, fact)

    def reject(
        self,
        submission_id: str,
        project_id: str,
        *,
        expected_version: int,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
        reason: str,
    ) -> KnowledgeSubmission:
        """Reject a pending submission with a mandatory review reason."""
        normalized_reason = self._reason(reason, required=True)
        current = self._reviewable(submission_id, project_id, expected_version, actor, scope)
        updated = current.transition(SubmissionStatus.REJECTED, at=self._clock.now())
        self._repository.transition(
            updated,
            self._event(
                updated,
                ApprovalAction.REJECTED,
                actor.actor_id,
                current.status,
                normalized_reason,
            ),
            expected_version=expected_version,
            expected_status=current.status,
        )
        return updated

    def _reviewable(
        self,
        submission_id: str,
        project_id: str,
        expected_version: int,
        actor: KnowledgeActor,
        scope: KnowledgeScope,
    ) -> KnowledgeSubmission:
        current = self._load(submission_id, project_id, actor, scope, KnowledgePermission.REVIEW)
        if current.submitter_id == actor.actor_id:
            raise KnowledgeAuthorizationError("Submitters cannot review their own contribution")
        if expected_version < 0 or current.version != expected_version:
            raise KnowledgeWorkflowConflictError("Knowledge submission version is stale")
        if current.status is not SubmissionStatus.SUBMITTED:
            raise KnowledgeWorkflowConflictError("Only submitted knowledge can be reviewed")
        return current

    def _reason(self, reason: str | None, *, required: bool) -> str | None:
        normalized = reason.strip() if reason else ""
        if required and not normalized:
            raise KnowledgeRequestError("A rejection reason is required")
        if len(normalized) > self._max_reason_characters:
            raise KnowledgeRequestError("Review reason exceeds the configured character limit")
        return normalized or None
