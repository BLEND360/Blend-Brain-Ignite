"""Snowflake persistence for gap assessments and governed knowledge."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, Self

from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_lifecycle.domain import (
    ApprovalEvent,
    ApprovedKnowledge,
    GapAssessment,
    GapField,
    GapKind,
    GapSeverity,
    GapStatus,
    KnowledgeGap,
    KnowledgeLifecycleError,
    KnowledgePersistenceError,
    KnowledgeSubmission,
    KnowledgeWorkflowConflictError,
    SubmissionStatus,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")


class CursorProtocol(Protocol):
    """Narrow Snowflake cursor surface used by Phase 7."""

    rowcount: int | None

    def execute(self, command: str, params: Any = None) -> Self:
        """Execute one statement."""
        ...

    def executemany(self, command: str, params: Any) -> Self:
        """Execute a statement for multiple rows."""
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
        """Return one bounded row."""
        ...

    def close(self) -> None:
        """Close the cursor."""
        ...


class ConnectionProtocol(Protocol):
    """Narrow transactional connection surface."""

    def cursor(self) -> CursorProtocol:
        """Create a cursor."""
        ...

    def commit(self) -> None:
        """Commit the transaction."""
        ...

    def rollback(self) -> None:
        """Roll back the transaction."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class ConnectionFactory(Protocol):
    """Create one isolated connection per repository operation."""

    def __call__(self) -> ConnectionProtocol:
        """Return a connection with explicit transaction control."""
        ...


class SnowflakeKnowledgeLifecycleRepository:
    """Transactional Phase 7 repository with optimistic workflow updates."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        database: str,
        schema: str = "KNOWLEDGE_BRAIN",
    ) -> None:
        for value in (database, schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        self._connection_factory = connection_factory
        self._namespace = f'"{database.upper()}"."{schema.upper()}"'

    def replace_assessment(self, assessment: GapAssessment) -> None:
        """Upsert one deterministic assessment and its gaps atomically."""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                f"""MERGE INTO {self._table("KNOWLEDGE_GAP_ASSESSMENTS")} target
                USING (SELECT %s assessment_id) source
                ON target.assessment_id = source.assessment_id
                WHEN MATCHED THEN UPDATE SET gap_count = %s, detected_at = %s,
                    status = 'completed'
                WHEN NOT MATCHED THEN INSERT
                    (assessment_id, policy_version, project_id, dna_id, status,
                     gap_count, detected_at)
                    VALUES (%s, %s, %s, %s, 'completed', %s, %s)""",
                (
                    assessment.assessment_id,
                    len(assessment.gaps),
                    assessment.detected_at,
                    assessment.assessment_id,
                    assessment.policy_version,
                    assessment.project_id,
                    assessment.dna_id,
                    len(assessment.gaps),
                    assessment.detected_at,
                ),
            )
            self._upsert_gaps(cursor, assessment)
            connection.commit()
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise self._error(
                "Snowflake gap assessment transaction failed", exception
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def get_gap(self, gap_id: str, project_id: str) -> KnowledgeGap | None:
        """Load a gap through both opaque ID and project boundary."""
        row = self._fetch_one(
            f"""SELECT gap_id, project_id, dna_id, field_name, gap_kind, severity,
                       explanation, observed_values, status, detected_at
                FROM {self._table("KNOWLEDGE_GAPS")}
                WHERE gap_id = %s AND project_id = %s""",
            (gap_id, project_id),
        )
        if row is None:
            return None
        if len(row) != 10:
            raise KnowledgePersistenceError("Snowflake returned an invalid knowledge-gap row")
        try:
            observed = json.loads(row[7]) if isinstance(row[7], str) else row[7]
        except json.JSONDecodeError as exception:
            raise KnowledgePersistenceError(
                "Knowledge-gap observed values contain invalid JSON"
            ) from exception
        if not isinstance(observed, (list, tuple)):
            raise KnowledgePersistenceError("Knowledge-gap observed values must be an array")
        try:
            return KnowledgeGap(
                gap_id=str(row[0]),
                project_id=str(row[1]),
                dna_id=str(row[2]),
                field=GapField(str(row[3])),
                kind=GapKind(str(row[4])),
                severity=GapSeverity(str(row[5])),
                explanation=str(row[6]),
                observed_values=tuple(str(item) for item in observed),
                status=GapStatus(str(row[8])),
                detected_at=row[9],
            )
        except (TypeError, ValueError) as exception:
            raise KnowledgePersistenceError(
                "Snowflake returned corrupt knowledge-gap data"
            ) from exception

    def create_submission(self, submission: KnowledgeSubmission, event: ApprovalEvent) -> None:
        """Atomically create a draft and its initial audit event."""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                f"""INSERT INTO {self._table("KNOWLEDGE_SUBMISSIONS")}
                (submission_id, project_id, gap_id, field_name, proposed_value, rationale,
                 source_reference, submitter_id, status, version, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                self._submission_values(submission),
            )
            self._insert_event(cursor, event)
            connection.commit()
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise self._error(
                "Snowflake knowledge capture transaction failed", exception
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def get_submission(self, submission_id: str, project_id: str) -> KnowledgeSubmission | None:
        """Load a contribution through both opaque ID and project boundary."""
        row = self._fetch_one(
            f"""SELECT submission_id, project_id, gap_id, field_name, proposed_value,
                       rationale, source_reference, submitter_id, status, version,
                       created_at, updated_at
                FROM {self._table("KNOWLEDGE_SUBMISSIONS")}
                WHERE submission_id = %s AND project_id = %s""",
            (submission_id, project_id),
        )
        if row is None:
            return None
        if len(row) != 12:
            raise KnowledgePersistenceError("Snowflake returned an invalid submission row")
        try:
            return KnowledgeSubmission(
                submission_id=str(row[0]),
                project_id=str(row[1]),
                gap_id=str(row[2]) if row[2] is not None else None,
                field=GapField(str(row[3])),
                proposed_value=str(row[4]),
                rationale=str(row[5]) if row[5] is not None else None,
                source_reference=str(row[6]) if row[6] is not None else None,
                submitter_id=str(row[7]),
                status=SubmissionStatus(str(row[8])),
                version=int(row[9]),
                created_at=row[10],
                updated_at=row[11],
            )
        except (TypeError, ValueError) as exception:
            raise KnowledgePersistenceError(
                "Snowflake returned corrupt submission data"
            ) from exception

    def transition(
        self,
        submission: KnowledgeSubmission,
        event: ApprovalEvent,
        *,
        expected_version: int,
        expected_status: SubmissionStatus,
        fact: ApprovedKnowledge | None = None,
    ) -> None:
        """Compare-and-set a transition and atomically persist every side effect."""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                f"""UPDATE {self._table("KNOWLEDGE_SUBMISSIONS")}
                SET status = %s, version = %s, updated_at = %s
                WHERE submission_id = %s AND project_id = %s
                    AND version = %s AND status = %s""",
                (
                    submission.status.value,
                    submission.version,
                    submission.updated_at,
                    submission.submission_id,
                    submission.project_id,
                    expected_version,
                    expected_status.value,
                ),
            )
            if cursor.rowcount != 1:
                raise KnowledgeWorkflowConflictError(
                    "Knowledge submission changed before the transition was committed"
                )
            self._insert_event(cursor, event)
            if fact is not None:
                self._insert_fact(cursor, fact)
                if submission.gap_id is not None:
                    cursor.execute(
                        f"""UPDATE {self._table("KNOWLEDGE_GAPS")}
                        SET status = 'resolved', resolved_by_fact_id = %s, resolved_at = %s
                        WHERE gap_id = %s AND project_id = %s AND status = 'open'""",
                        (
                            fact.fact_id,
                            fact.approved_at,
                            submission.gap_id,
                            submission.project_id,
                        ),
                    )
            connection.commit()
        except KnowledgeLifecycleError:
            if connection is not None:
                connection.rollback()
            raise
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise self._error(
                "Snowflake approval workflow transaction failed", exception
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _upsert_gaps(self, cursor: CursorProtocol, assessment: GapAssessment) -> None:
        rows = [
            (
                gap.gap_id,
                assessment.assessment_id,
                gap.project_id,
                gap.dna_id,
                gap.field.value,
                gap.kind.value,
                gap.severity.value,
                gap.explanation,
                json.dumps(gap.observed_values, separators=(",", ":")),
                gap.status.value,
                gap.detected_at,
            )
            for gap in assessment.gaps
        ]
        if rows:
            cursor.executemany(
                f"""MERGE INTO {self._table("KNOWLEDGE_GAPS")} target
                USING (SELECT %s gap_id, %s assessment_id, %s project_id, %s dna_id,
                              %s field_name, %s gap_kind, %s severity, %s explanation,
                              PARSE_JSON(%s) observed_values, %s status, %s detected_at) source
                ON target.gap_id = source.gap_id
                WHEN MATCHED THEN UPDATE SET severity = source.severity,
                    explanation = source.explanation, observed_values = source.observed_values,
                    detected_at = source.detected_at
                WHEN NOT MATCHED THEN INSERT
                    (gap_id, assessment_id, project_id, dna_id, field_name, gap_kind,
                     severity, explanation, observed_values, status, detected_at)
                    VALUES (source.gap_id, source.assessment_id, source.project_id,
                            source.dna_id, source.field_name, source.gap_kind, source.severity,
                            source.explanation, source.observed_values, source.status,
                            source.detected_at)""",
                rows,
            )

    def _fetch_one(self, command: str, params: tuple[object, ...]) -> tuple[Any, ...] | None:
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(command, params)
            return cursor.fetchone()
        except SnowflakeError as exception:
            raise self._error("Snowflake knowledge lifecycle read failed", exception) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _insert_event(self, cursor: CursorProtocol, event: ApprovalEvent) -> None:
        cursor.execute(
            f"""INSERT INTO {self._table("KNOWLEDGE_APPROVAL_EVENTS")}
            (event_id, submission_id, project_id, action, actor_id, from_status,
             to_status, reason, submission_version, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                event.event_id,
                event.submission_id,
                event.project_id,
                event.action.value,
                event.actor_id,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                event.reason,
                event.submission_version,
                event.occurred_at,
            ),
        )

    def _insert_fact(self, cursor: CursorProtocol, fact: ApprovedKnowledge) -> None:
        cursor.execute(
            f"""INSERT INTO {self._table("APPROVED_KNOWLEDGE")}
            (fact_id, submission_id, project_id, field_name, fact_value,
             source_reference, approved_by, approved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                fact.fact_id,
                fact.submission_id,
                fact.project_id,
                fact.field.value,
                fact.value,
                fact.source_reference,
                fact.approved_by,
                fact.approved_at,
            ),
        )

    @staticmethod
    def _submission_values(submission: KnowledgeSubmission) -> tuple[object, ...]:
        return (
            submission.submission_id,
            submission.project_id,
            submission.gap_id,
            submission.field.value,
            submission.proposed_value,
            submission.rationale,
            submission.source_reference,
            submission.submitter_id,
            submission.status.value,
            submission.version,
            submission.created_at,
            submission.updated_at,
        )

    def _table(self, table: str) -> str:
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError(f"Unsafe Snowflake table identifier: {table}")
        return f'{self._namespace}."{table}"'

    @staticmethod
    def _error(message: str, exception: SnowflakeError) -> KnowledgePersistenceError:
        return KnowledgePersistenceError(
            message,
            sqlstate=exception.sqlstate,
            errno=exception.errno,
        )
