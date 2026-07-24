"""Knowledge capture and approval workflow tests."""

from dataclasses import replace

import pytest

from blend_brain.knowledge_lifecycle.application import (
    CaptureKnowledgeCommand,
    CaptureLimits,
    KnowledgeApprovalService,
    KnowledgeCaptureService,
    KnowledgeGapDetectionService,
    KnowledgeGapDetector,
)
from blend_brain.knowledge_lifecycle.domain import (
    ApprovalAction,
    GapField,
    GapStatus,
    KnowledgeActor,
    KnowledgeAuthorizationError,
    KnowledgeNotFoundError,
    KnowledgePermission,
    KnowledgeRequestError,
    KnowledgeScope,
    KnowledgeWorkflowConflictError,
    SubmissionStatus,
)
from tests.unit.knowledge_enrichment.helpers import dna
from tests.unit.knowledge_lifecycle.helpers import (
    FixedClock,
    MemoryRepository,
    SequenceIdentifiers,
)


def actor(actor_id: str, permission: KnowledgePermission) -> KnowledgeActor:
    """Build an actor with one explicit permission."""
    return KnowledgeActor(actor_id, frozenset({permission}))


def services() -> tuple[
    MemoryRepository,
    KnowledgeCaptureService,
    KnowledgeApprovalService,
    KnowledgeScope,
]:
    """Build an isolated workflow fixture."""
    repository = MemoryRepository()
    identifiers = SequenceIdentifiers()
    clock = FixedClock()
    return (
        repository,
        KnowledgeCaptureService(repository, clock, identifiers),
        KnowledgeApprovalService(repository, clock, identifiers),
        KnowledgeScope(("project-1",)),
    )


def test_capture_submit_and_independent_approval_create_governed_fact() -> None:
    repository, capture, approval, scope = services()
    assessment = KnowledgeGapDetectionService(
        KnowledgeGapDetector(), repository, FixedClock()
    ).assess(dna())
    gap = next(item for item in assessment.gaps if item.field is GapField.CLIENT_NAME)
    submitter = actor("employee-1", KnowledgePermission.CAPTURE)
    reviewer = actor("reviewer-1", KnowledgePermission.REVIEW)

    draft = capture.capture(
        CaptureKnowledgeCommand(
            project_id="project-1",
            field=GapField.CLIENT_NAME,
            proposed_value=" Example Co ",
            gap_id=gap.gap_id,
            rationale="Known account",
            source_reference="CRM account 42",
        ),
        actor=submitter,
        scope=scope,
    )
    submitted = capture.submit(
        draft.submission_id,
        draft.project_id,
        expected_version=0,
        actor=submitter,
        scope=scope,
    )
    outcome = approval.approve(
        submitted.submission_id,
        submitted.project_id,
        expected_version=1,
        actor=reviewer,
        scope=scope,
        reason="Verified",
    )

    assert draft.proposed_value == "Example Co"
    assert outcome.submission.status is SubmissionStatus.APPROVED
    assert outcome.submission.version == 2
    assert outcome.fact.value == "Example Co"
    assert repository.facts == [outcome.fact]
    assert [event.action for event in repository.events] == [
        ApprovalAction.CAPTURED,
        ApprovalAction.SUBMITTED,
        ApprovalAction.APPROVED,
    ]


def test_reviewer_can_reject_and_submitter_can_withdraw() -> None:
    repository, capture, approval, scope = services()
    submitter = actor("employee-1", KnowledgePermission.CAPTURE)
    reviewer = actor("reviewer-1", KnowledgePermission.REVIEW)
    draft = capture.capture(
        CaptureKnowledgeCommand("project-1", GapField.OUTCOMES, "Reduced cycle time"),
        actor=submitter,
        scope=scope,
    )
    submitted = capture.submit(
        draft.submission_id,
        "project-1",
        expected_version=0,
        actor=submitter,
        scope=scope,
    )
    rejected = approval.reject(
        submitted.submission_id,
        "project-1",
        expected_version=1,
        actor=reviewer,
        scope=scope,
        reason="No supporting source",
    )
    assert rejected.status is SubmissionStatus.REJECTED

    other = capture.capture(
        CaptureKnowledgeCommand("project-1", GapField.EXPERTS, "Jane Expert"),
        actor=submitter,
        scope=scope,
    )
    withdrawn = capture.withdraw(
        other.submission_id,
        "project-1",
        expected_version=0,
        actor=submitter,
        scope=scope,
        reason="Duplicate",
    )
    assert withdrawn.status is SubmissionStatus.WITHDRAWN
    assert repository.events[-1].reason == "Duplicate"


def test_workflow_rejects_self_approval_wrong_scope_and_stale_versions() -> None:
    _, capture, approval, scope = services()
    submitter = KnowledgeActor(
        "employee-1",
        frozenset({KnowledgePermission.CAPTURE, KnowledgePermission.REVIEW}),
    )
    draft = capture.capture(
        CaptureKnowledgeCommand("project-1", GapField.SUMMARY, "Summary"),
        actor=submitter,
        scope=scope,
    )
    with pytest.raises(KnowledgeWorkflowConflictError, match="stale"):
        capture.submit(
            draft.submission_id,
            "project-1",
            expected_version=2,
            actor=submitter,
            scope=scope,
        )
    submitted = capture.submit(
        draft.submission_id,
        "project-1",
        expected_version=0,
        actor=submitter,
        scope=scope,
    )
    with pytest.raises(KnowledgeAuthorizationError, match="own"):
        approval.approve(
            submitted.submission_id,
            "project-1",
            expected_version=1,
            actor=submitter,
            scope=scope,
        )
    with pytest.raises(KnowledgeAuthorizationError):
        capture.capture(
            CaptureKnowledgeCommand("project-2", GapField.SUMMARY, "Summary"),
            actor=submitter,
            scope=scope,
        )


def test_capture_validates_limits_gap_link_and_missing_records() -> None:
    repository, capture, approval, scope = services()
    submitter = actor("employee-1", KnowledgePermission.CAPTURE)
    reviewer = actor("reviewer-1", KnowledgePermission.REVIEW)
    limited = KnowledgeCaptureService(
        repository,
        FixedClock(),
        SequenceIdentifiers(),
        CaptureLimits(5, 5, 5),
    )
    with pytest.raises(KnowledgeRequestError, match="cannot be empty"):
        limited.capture(
            CaptureKnowledgeCommand("project-1", GapField.SUMMARY, " "),
            actor=submitter,
            scope=scope,
        )
    with pytest.raises(KnowledgeRequestError, match="character limit"):
        limited.capture(
            CaptureKnowledgeCommand("project-1", GapField.SUMMARY, "too long"),
            actor=submitter,
            scope=scope,
        )
    assessment = KnowledgeGapDetectionService(
        KnowledgeGapDetector(), repository, FixedClock()
    ).assess(dna())
    client_gap = next(item for item in assessment.gaps if item.field is GapField.CLIENT_NAME)
    with pytest.raises(KnowledgeRequestError, match="does not match"):
        capture.capture(
            CaptureKnowledgeCommand(
                "project-1", GapField.SUMMARY, "Value", gap_id=client_gap.gap_id
            ),
            actor=submitter,
            scope=scope,
        )
    repository.gaps[(client_gap.gap_id, client_gap.project_id)] = replace(
        client_gap, status=GapStatus.RESOLVED
    )
    with pytest.raises(KnowledgeWorkflowConflictError, match="Resolved"):
        capture.capture(
            CaptureKnowledgeCommand(
                "project-1", GapField.CLIENT_NAME, "Example Co", gap_id=client_gap.gap_id
            ),
            actor=submitter,
            scope=scope,
        )
    with pytest.raises(KnowledgeNotFoundError, match="gap"):
        capture.capture(
            CaptureKnowledgeCommand("project-1", GapField.SUMMARY, "Value", gap_id="missing"),
            actor=submitter,
            scope=scope,
        )
    with pytest.raises(KnowledgeNotFoundError, match="submission"):
        approval.reject(
            "missing",
            "project-1",
            expected_version=0,
            actor=reviewer,
            scope=scope,
            reason="Invalid",
        )
    with pytest.raises(KnowledgeRequestError, match="reason"):
        approval.reject(
            "missing",
            "project-1",
            expected_version=0,
            actor=reviewer,
            scope=scope,
            reason=" ",
        )
    short_reviews = KnowledgeApprovalService(
        repository,
        FixedClock(),
        SequenceIdentifiers(),
        max_reason_characters=3,
    )
    draft = capture.capture(
        CaptureKnowledgeCommand("project-1", GapField.SUMMARY, "Value"),
        actor=submitter,
        scope=scope,
    )
    submitted = capture.submit(
        draft.submission_id,
        "project-1",
        expected_version=0,
        actor=submitter,
        scope=scope,
    )
    with pytest.raises(KnowledgeRequestError, match="character limit"):
        short_reviews.approve(
            submitted.submission_id,
            "project-1",
            expected_version=1,
            actor=reviewer,
            scope=scope,
            reason="long",
        )


def test_domain_scope_actor_and_limits_validate_invariants() -> None:
    with pytest.raises(ValueError, match="at least one"):
        KnowledgeScope(())
    with pytest.raises(ValueError, match="actor_id"):
        KnowledgeActor(" ", frozenset())
    with pytest.raises(ValueError, match="greater than zero"):
        CaptureLimits(max_value_characters=0)
    with pytest.raises(ValueError, match="greater than zero"):
        KnowledgeApprovalService(
            MemoryRepository(),
            FixedClock(),
            SequenceIdentifiers(),
            max_reason_characters=0,
        )
