"""Phase 7 Snowflake repository and migration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self, cast

import pytest
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_lifecycle.application import KnowledgeGapDetector
from blend_brain.knowledge_lifecycle.domain import (
    ApprovalAction,
    ApprovalEvent,
    ApprovedKnowledge,
    GapField,
    KnowledgePersistenceError,
    KnowledgeSubmission,
    KnowledgeWorkflowConflictError,
    SubmissionStatus,
)
from blend_brain.knowledge_lifecycle.infrastructure.snowflake import (
    ConnectionFactory,
    ConnectionProtocol,
    SnowflakeKnowledgeLifecycleRepository,
)
from tests.unit.knowledge_enrichment.helpers import dna
from tests.unit.knowledge_lifecycle.helpers import NOW


class Cursor:
    """Record SQL and return queued rows."""

    def __init__(self, rows: list[tuple[Any, ...] | None] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[tuple[str, Any]] = []
        self.batches: list[tuple[str, Any]] = []
        self.rowcount: int | None = 1
        self.failure: SnowflakeError | None = None
        self.closed = False

    def execute(self, command: str, params: Any = None) -> Self:
        if self.failure:
            raise self.failure
        self.executed.append((command, params))
        return self

    def executemany(self, command: str, params: Any) -> Self:
        if self.failure:
            raise self.failure
        self.batches.append((command, params))
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.rows.pop(0)

    def close(self) -> None:
        self.closed = True


class Connection:
    """Record transaction lifecycle."""

    def __init__(self, cursor: Cursor) -> None:
        self.test_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> Cursor:
        return self.test_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def factory(connection: Connection) -> ConnectionFactory:
    """Cast the fake factory to the narrow repository protocol."""
    return lambda: cast("ConnectionProtocol", connection)


def repository(connection: Connection) -> SnowflakeKnowledgeLifecycleRepository:
    """Build a repository around a fake connection."""
    return SnowflakeKnowledgeLifecycleRepository(factory(connection), database="BLEND_BRAIN")


def submission(
    status: SubmissionStatus = SubmissionStatus.DRAFT, version: int = 0
) -> KnowledgeSubmission:
    """Return one representative submission."""
    return KnowledgeSubmission(
        submission_id="submission-1",
        project_id="project-1",
        gap_id="gap-1",
        field=GapField.CLIENT_NAME,
        proposed_value="Example Co",
        rationale="CRM match",
        source_reference="CRM 42",
        submitter_id="employee-1",
        status=status,
        version=version,
        created_at=NOW,
        updated_at=NOW,
    )


def event(action: ApprovalAction, status: SubmissionStatus, version: int) -> ApprovalEvent:
    """Return an audit event aligned with a submission."""
    return ApprovalEvent(
        event_id="event-1",
        submission_id="submission-1",
        project_id="project-1",
        action=action,
        actor_id="reviewer-1",
        from_status=SubmissionStatus.SUBMITTED,
        to_status=status,
        reason=None,
        submission_version=version,
        occurred_at=NOW,
    )


def test_repository_persists_assessment_and_capture_transactions() -> None:
    assessment_cursor = Cursor()
    assessment_connection = Connection(assessment_cursor)
    assessment = KnowledgeGapDetector().detect(dna(), detected_at=NOW)

    repository(assessment_connection).replace_assessment(assessment)

    assert assessment_connection.committed
    assert any("GAP_ASSESSMENTS" in sql for sql, _ in assessment_cursor.executed)
    assert any("KNOWLEDGE_GAPS" in sql for sql, _ in assessment_cursor.batches)

    capture_cursor = Cursor()
    capture_connection = Connection(capture_cursor)
    draft = submission()
    repository(capture_connection).create_submission(
        draft, event(ApprovalAction.CAPTURED, SubmissionStatus.DRAFT, 0)
    )
    assert capture_connection.committed
    assert any("KNOWLEDGE_SUBMISSIONS" in sql for sql, _ in capture_cursor.executed)
    assert any("APPROVAL_EVENTS" in sql for sql, _ in capture_cursor.executed)


def test_repository_maps_scoped_gap_and_submission_rows() -> None:
    observed = json.dumps(["Retail"])
    gap_row = (
        "gap-1",
        "project-1",
        "dna-1",
        "industry",
        "low_confidence",
        "medium",
        "Needs verification",
        observed,
        "open",
        NOW,
    )
    loaded_gap = repository(Connection(Cursor([gap_row]))).get_gap("gap-1", "project-1")
    assert loaded_gap is not None
    assert loaded_gap.observed_values == ("Retail",)

    draft = submission()
    submission_row = (
        draft.submission_id,
        draft.project_id,
        draft.gap_id,
        draft.field.value,
        draft.proposed_value,
        draft.rationale,
        draft.source_reference,
        draft.submitter_id,
        draft.status.value,
        draft.version,
        draft.created_at,
        draft.updated_at,
    )
    loaded = repository(Connection(Cursor([submission_row]))).get_submission(
        draft.submission_id, draft.project_id
    )
    assert loaded == draft
    assert repository(Connection(Cursor([None]))).get_gap("missing", "project-1") is None


def test_approval_atomically_creates_fact_and_resolves_gap() -> None:
    cursor = Cursor()
    connection = Connection(cursor)
    approved = submission(SubmissionStatus.APPROVED, 2)
    fact = ApprovedKnowledge(
        "fact-1",
        approved.submission_id,
        approved.project_id,
        approved.field,
        approved.proposed_value,
        approved.source_reference,
        "reviewer-1",
        NOW,
    )

    repository(connection).transition(
        approved,
        event(ApprovalAction.APPROVED, SubmissionStatus.APPROVED, 2),
        expected_version=1,
        expected_status=SubmissionStatus.SUBMITTED,
        fact=fact,
    )

    assert connection.committed
    assert any("APPROVED_KNOWLEDGE" in sql for sql, _ in cursor.executed)
    assert any("KNOWLEDGE_GAPS" in sql and "resolved" in sql for sql, _ in cursor.executed)


def test_transition_conflict_and_snowflake_failure_roll_back() -> None:
    conflict_cursor = Cursor()
    conflict_cursor.rowcount = 0
    conflict_connection = Connection(conflict_cursor)
    with pytest.raises(KnowledgeWorkflowConflictError):
        repository(conflict_connection).transition(
            submission(SubmissionStatus.SUBMITTED, 1),
            event(ApprovalAction.SUBMITTED, SubmissionStatus.SUBMITTED, 1),
            expected_version=0,
            expected_status=SubmissionStatus.DRAFT,
        )
    assert conflict_connection.rolled_back

    failed_cursor = Cursor()
    failed_cursor.failure = SnowflakeError(msg="failed", errno=10, sqlstate="XX000")
    failed_connection = Connection(failed_cursor)
    with pytest.raises(KnowledgePersistenceError) as captured:
        repository(failed_connection).replace_assessment(
            KnowledgeGapDetector().detect(dna(), detected_at=NOW)
        )
    assert captured.value.context["sqlstate"] == "XX000"
    assert failed_connection.rolled_back
    assert failed_connection.closed


def test_repository_validates_identifiers_and_migration_contract() -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeKnowledgeLifecycleRepository(factory(Connection(Cursor())), database="bad-name")

    migration = (
        Path(__file__).parents[3] / "migrations" / "005_phase_7_knowledge_lifecycle.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_GAP_ASSESSMENTS" in migration
    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_GAPS" in migration
    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_SUBMISSIONS" in migration
    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_APPROVAL_EVENTS" in migration
    assert "CREATE TABLE IF NOT EXISTS APPROVED_KNOWLEDGE" in migration
    assert "UNIQUE (SUBMISSION_ID)" in migration


def test_repository_rejects_corrupt_read_rows() -> None:
    corrupt_gap = (
        "gap",
        "project-1",
        "dna",
        "not-a-field",
        "missing",
        "high",
        "Explanation",
        "[]",
        "open",
        NOW,
    )
    with pytest.raises(KnowledgePersistenceError, match="corrupt"):
        repository(Connection(Cursor([corrupt_gap]))).get_gap("gap", "project-1")
    with pytest.raises(KnowledgePersistenceError, match="invalid JSON"):
        repository(Connection(Cursor([(*corrupt_gap[:7], "not-json", *corrupt_gap[8:])]))).get_gap(
            "gap", "project-1"
        )

    corrupt_submission = (
        "submission",
        "project-1",
        None,
        "not-a-field",
        "Value",
        None,
        None,
        "employee",
        "draft",
        0,
        NOW,
        NOW,
    )
    with pytest.raises(KnowledgePersistenceError, match="corrupt"):
        repository(Connection(Cursor([corrupt_submission]))).get_submission(
            "submission", "project-1"
        )
