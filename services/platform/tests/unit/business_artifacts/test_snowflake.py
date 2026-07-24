"""Phase 8 Snowflake repository and migration tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Self, cast

import pytest
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.business_artifacts.domain import (
    ArtifactExport,
    ArtifactKind,
    ArtifactPersistenceError,
    ArtifactScope,
    ArtifactSourceError,
    ProjectOnePagerArtifact,
    ProposalArtifact,
)
from blend_brain.business_artifacts.infrastructure.snowflake import (
    ConnectionFactory,
    ConnectionProtocol,
    SnowflakeBusinessArtifactRepository,
)
from tests.unit.business_artifacts.helpers import NOW, one_pager, project_source, proposal


class Cursor:
    """Record SQL and return configured rows."""

    def __init__(
        self,
        *,
        one_rows: list[tuple[Any, ...] | None] | None = None,
        all_rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self.one_rows = one_rows or []
        self.all_rows = all_rows or []
        self.executed: list[tuple[str, Any]] = []
        self.batches: list[tuple[str, Any]] = []
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
        return self.one_rows.pop(0)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.all_rows

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
    """Cast the fake factory to the repository protocol."""
    return lambda: cast("ConnectionProtocol", connection)


def repository(connection: Connection) -> SnowflakeBusinessArtifactRepository:
    """Build a repository around one fake connection."""
    return SnowflakeBusinessArtifactRepository(factory(connection), database="BLEND_BRAIN")


def artifact_row(artifact: ProposalArtifact | ProjectOnePagerArtifact) -> tuple[object, ...]:
    """Serialize an artifact as Snowflake would return it."""
    return (
        artifact.artifact_id,
        artifact.request_id,
        json.dumps(artifact.source_project_ids),
        json.dumps(asdict(artifact.brief)),
        artifact.title,
        artifact.subtitle,
        json.dumps([asdict(section) for section in artifact.sections]),
        artifact.model,
        artifact.prompt_version,
        artifact.status.value,
        artifact.content_sha256,
        artifact.created_by,
        artifact.created_at,
    )


def test_loads_bounded_current_project_sources() -> None:
    cursor = Cursor(
        all_rows=[("project-1", "document-1", 2, "case-study.md", "Grounded source text")]
    )
    result = repository(Connection(cursor)).load_project_sources(("project-1",))

    assert result[0].source_id == "P1"
    assert result[0].section_sequence == 2
    assert cursor.executed[0][1] == ("project-1", 100)


def test_persists_artifact_and_resolved_citations_atomically() -> None:
    artifact = proposal()
    cursor = Cursor(one_rows=[(artifact.content_sha256,)])
    connection = Connection(cursor)

    repository(connection).persist(artifact, (project_source(),))

    assert connection.committed
    assert any("MERGE INTO" in sql and "PROPOSALS" in sql for sql, _ in cursor.executed)
    assert any("ARTIFACT_CITATIONS" in sql for sql, _ in cursor.batches)
    citation_rows = cursor.batches[0][1]
    assert citation_rows[0][8] == "project-1"


def test_persist_rejects_idempotency_collision_and_missing_citation_source() -> None:
    collision = Connection(Cursor(one_rows=[("different",)]))
    with pytest.raises(ArtifactPersistenceError, match="different"):
        repository(collision).persist(proposal(), (project_source(),))
    assert collision.rolled_back

    missing = Connection(Cursor(one_rows=[(proposal().content_sha256,)]))
    with pytest.raises(ArtifactSourceError, match="disappeared"):
        repository(missing).persist(proposal(), ())
    assert missing.rolled_back


def test_maps_proposal_one_pager_idempotency_and_scoped_reads() -> None:
    proposal_result = repository(
        Connection(Cursor(one_rows=[artifact_row(proposal())]))
    ).find_by_request("request-1", ArtifactKind.PROPOSAL, "employee-1", ("project-1",))
    one_pager_result = repository(
        Connection(Cursor(one_rows=[artifact_row(one_pager())]))
    ).get_artifact(
        "one-pager-1",
        ArtifactKind.PROJECT_ONE_PAGER,
        ArtifactScope(("project-1",)),
    )

    assert isinstance(proposal_result, ProposalArtifact)
    assert isinstance(one_pager_result, ProjectOnePagerArtifact)
    assert one_pager_result.brief.project_id == "project-1"
    assert (
        repository(Connection(Cursor(one_rows=[None]))).get_artifact(
            "missing", ArtifactKind.PROPOSAL, ArtifactScope(("project-1",))
        )
        is None
    )


def test_records_export_and_translates_snowflake_errors() -> None:
    cursor = Cursor()
    connection = Connection(cursor)
    export = ArtifactExport(
        "export-1",
        "artifact-1",
        ArtifactKind.PROPOSAL,
        "/local/artifacts",
        "key.pdf",
        "application/pdf",
        100,
        "a" * 64,
        "employee-1",
        NOW,
    )
    repository(connection).record_export(export)
    assert connection.committed
    assert any("ARTIFACT_EXPORTS" in sql for sql, _ in cursor.executed)

    failed_cursor = Cursor()
    failed_cursor.failure = SnowflakeError(msg="failed", errno=10, sqlstate="XX000")
    failed = Connection(failed_cursor)
    with pytest.raises(ArtifactPersistenceError) as captured:
        repository(failed).record_export(export)
    assert captured.value.context["sqlstate"] == "XX000"
    assert failed.rolled_back


def test_rejects_corrupt_rows_identifiers_and_migration_regressions() -> None:
    corrupt = list(artifact_row(proposal()))
    corrupt[2] = "not-json"
    with pytest.raises(ArtifactPersistenceError):
        repository(Connection(Cursor(one_rows=[tuple(corrupt)]))).find_by_request(
            "request", ArtifactKind.PROPOSAL, "actor", ("project-1",)
        )
    with pytest.raises(ArtifactSourceError):
        repository(Connection(Cursor(all_rows=[("bad",)]))).load_project_sources(("project-1",))
    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeBusinessArtifactRepository(factory(Connection(Cursor())), database="bad-name")
    with pytest.raises(ValueError, match="greater than zero"):
        SnowflakeBusinessArtifactRepository(
            factory(Connection(Cursor())), database="VALID", max_sections_per_project=0
        )

    migration = (
        Path(__file__).parents[3] / "migrations" / "006_phase_8_business_artifacts.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS PROPOSALS" in migration
    assert "CREATE TABLE IF NOT EXISTS PROJECT_ONE_PAGERS" in migration
    assert "CREATE TABLE IF NOT EXISTS ARTIFACT_CITATIONS" in migration
    assert "CREATE TABLE IF NOT EXISTS ARTIFACT_EXPORTS" in migration
