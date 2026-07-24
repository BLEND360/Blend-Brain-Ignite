"""Transactional Snowflake repository tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_enrichment.domain import PersistenceError
from blend_brain.knowledge_enrichment.infrastructure.snowflake import (
    ConnectionProtocol,
    SnowflakeConnectionConfig,
    SnowflakeConnectionFactory,
    SnowflakeKnowledgeRepository,
)
from tests.unit.knowledge_enrichment.helpers import bundle


class FakeCursor:
    """Capture bound statements and optionally fail."""

    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.executed: list[tuple[str, Any]] = []
        self.batches: list[tuple[str, Any]] = []
        self.rows = rows or []
        self.closed = False
        self.failure: SnowflakeError | None = None

    def execute(self, command: str, params: Any = None) -> Self:
        if self.failure is not None:
            raise self.failure
        self.executed.append((command, params))
        return self

    def executemany(self, command: str, params: Any) -> Self:
        self.batches.append((command, params))
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    """Record transaction lifecycle operations."""

    def __init__(self, cursor: FakeCursor) -> None:
        self.test_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.test_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def repository(connection: FakeConnection) -> SnowflakeKnowledgeRepository:
    """Create a repository around a fake connection."""
    return SnowflakeKnowledgeRepository(
        lambda: cast("ConnectionProtocol", connection),
        database="BLEND_BRAIN",
    )


def test_repository_commits_complete_parameter_bound_bundle() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    repository(connection).persist(bundle())

    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert cursor.closed is True
    assert cursor.executed[0][0] == "BEGIN"
    assert any("MERGE INTO" in sql and "PROJECTS" in sql for sql, _ in cursor.executed)
    assert any("PARSE_JSON" in sql and "PROJECT_DNA" in sql for sql, _ in cursor.executed)
    assert any("VECTOR(FLOAT, 3072)" in sql for sql, _ in cursor.executed)
    assert all(params is not None for _, params in cursor.executed[1:])
    document_parameters = next(
        params for sql, params in cursor.executed if "MERGE INTO" in sql and "DOCUMENTS" in sql
    )
    assert document_parameters["source_created_at"] == bundle().profile.created_at
    assert document_parameters["source_modified_at"] == bundle().profile.modified_at


def test_repository_loads_completed_document_ids_and_closes_resources() -> None:
    cursor = FakeCursor([("document-1",), ("document-2",), ("document-1",)])
    connection = FakeConnection(cursor)

    result = repository(connection).completed_document_ids()

    assert result == frozenset({"document-1", "document-2"})
    assert cursor.executed[0][1] == ("completed",)
    assert cursor.closed
    assert connection.closed


def test_repository_skips_empty_batches_and_validates_dimensions() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    empty = bundle(include_embedding=False)

    repository(connection).persist(empty)

    assert len(cursor.batches) == 1
    with pytest.raises(PersistenceError, match="dimensions"):
        repository(FakeConnection(FakeCursor())).persist(bundle(dimensions=3))


def test_repository_rolls_back_and_translates_snowflake_errors() -> None:
    cursor = FakeCursor()
    cursor.failure = SnowflakeError(msg="failed", errno=100, sqlstate="XX000")
    connection = FakeConnection(cursor)

    with pytest.raises(PersistenceError) as captured:
        repository(connection).persist(bundle())

    assert captured.value.context == {"run_id": "run-id", "sqlstate": "XX000", "errno": 100}
    assert connection.rolled_back is True
    assert connection.closed is True


def test_repository_translates_connection_failure() -> None:
    failure = SnowflakeError(msg="unavailable", errno=101, sqlstate="08001")

    def fail() -> ConnectionProtocol:
        raise failure

    snowflake_repository = SnowflakeKnowledgeRepository(fail, database="BLEND_BRAIN")
    with pytest.raises(PersistenceError) as captured:
        snowflake_repository.persist(bundle())

    assert captured.value.context["sqlstate"] == "08001"


@pytest.mark.parametrize("identifier", ["bad-name", "name;drop", ""])
def test_snowflake_identifiers_are_allowlist_validated(identifier: str) -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeKnowledgeRepository(lambda: cast("ConnectionProtocol", None), database=identifier)
    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeConnectionConfig(
            account="account",
            user="user",
            warehouse="warehouse",
            database=identifier,
            password=uuid4().hex,
        )


def test_connection_config_requires_authentication() -> None:
    with pytest.raises(ValueError, match="password or private key"):
        SnowflakeConnectionConfig(
            account="account",
            user="user",
            warehouse="warehouse",
            database="database",
        )


def test_connection_factory_passes_secure_transactional_configuration() -> None:
    config = SnowflakeConnectionConfig(
        account="account",
        user="user",
        warehouse="warehouse",
        database="database",
        schema="knowledge_brain",
        role="role",
        private_key_file="/secrets/key.p8",
        private_key_file_password=uuid4().hex,
    )
    connection = FakeConnection(FakeCursor())
    with patch(
        "blend_brain.knowledge_enrichment.infrastructure.snowflake.snowflake.connector.connect",
        return_value=connection,
    ) as connect:
        result = SnowflakeConnectionFactory(config)()

    assert result is connection
    kwargs = connect.call_args.kwargs
    assert kwargs["autocommit"] is False
    assert kwargs["private_key_file"] == "/secrets/key.p8"
    assert kwargs["session_parameters"]["QUERY_TAG"] == "blend-knowledge-brain:phase-3"


def test_phase_3_migration_defines_vector_and_audit_tables() -> None:
    migration = (Path(__file__).parents[3] / "migrations" / "003_phase_3_enrichment.sql").read_text(
        encoding="utf-8"
    )

    assert "VECTOR(FLOAT, 3072)" in migration
    assert "CREATE TABLE IF NOT EXISTS PROJECT_DNA" in migration
    assert "CREATE TABLE IF NOT EXISTS ENRICHMENT_RUNS" in migration
