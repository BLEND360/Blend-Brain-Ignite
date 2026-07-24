"""Phase 6 Snowflake repository and migration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self, cast

import pytest
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.organizational_intelligence.application import KnowledgeGraphProjector
from blend_brain.organizational_intelligence.domain import (
    GraphPersistenceError,
    IntelligenceCorpusError,
    IntelligenceScope,
)
from blend_brain.organizational_intelligence.infrastructure.snowflake import (
    ConnectionFactory,
    ConnectionProtocol,
    SnowflakeIntelligenceRepository,
    SnowflakeKnowledgeGraphRepository,
)
from tests.unit.knowledge_enrichment.helpers import dna


class Cursor:
    """Transactional cursor with queued query result sets."""

    def __init__(self, result_sets: list[list[tuple[Any, ...]]] | None = None) -> None:
        self.result_sets = result_sets or []
        self.executed: list[tuple[str, Any]] = []
        self.batches: list[tuple[str, Any]] = []
        self.closed = False
        self.error: SnowflakeError | None = None

    def execute(self, command: str, params: Any = None) -> Self:
        if self.error:
            raise self.error
        self.executed.append((command, params))
        return self

    def executemany(self, command: str, params: Any) -> Self:
        if self.error:
            raise self.error
        self.batches.append((command, params))
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.result_sets.pop(0)

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
    """Return a protocol-cast connection factory."""
    return lambda: cast("ConnectionProtocol", connection)


def test_graph_repository_commits_nodes_edges_evidence_and_audit() -> None:
    cursor = Cursor()
    connection = Connection(cursor)
    snapshot = KnowledgeGraphProjector().project(dna())
    repository = SnowflakeKnowledgeGraphRepository(factory(connection), database="BLEND_BRAIN")

    repository.replace(snapshot)

    assert connection.committed
    assert not connection.rolled_back
    assert cursor.closed
    assert connection.closed
    assert any("KNOWLEDGE_GRAPH_NODES" in command for command, _ in cursor.executed)
    edge_parameters = next(
        params
        for command, params in cursor.executed
        if "INSERT INTO" in command and "GRAPH_EDGES" in command
    )
    assert json.loads(edge_parameters[7])[0]["document_id"] == dna().document_id
    assert any("GRAPH_PROJECTION_RUNS" in command for command, _ in cursor.executed)


def test_graph_repository_rolls_back_and_translates_snowflake_failure() -> None:
    cursor = Cursor()
    cursor.error = SnowflakeError(msg="failed", errno=10, sqlstate="XX000")
    connection = Connection(cursor)
    repository = SnowflakeKnowledgeGraphRepository(factory(connection), database="BLEND_BRAIN")

    with pytest.raises(GraphPersistenceError) as captured:
        repository.replace(KnowledgeGraphProjector().project(dna()))

    assert captured.value.context["sqlstate"] == "XX000"
    assert connection.rolled_back
    assert connection.closed


def test_intelligence_repository_scopes_and_maps_vectors_graph_and_experts() -> None:
    evidence = [{"document_id": "document-1", "section_sequence": 2, "quote": "Jane led"}]
    project_rows = [("project-1", "dna-1", "Retail Forecasting", [1.0, 0.0, 0.0])]
    graph_rows = [
        ("project-1", "in_industry", "industry-1", "Retail", []),
        ("project-1", "uses_technology", "tech-1", "Snowflake", []),
        ("project-1", "has_capability", "cap-1", "Forecasting", []),
        ("project-1", "has_use_case", "use-1", "Demand Forecasting", []),
        ("project-1", "uses_cloud_platform", "cloud-1", "AWS", []),
        ("project-1", "involved_expert", "expert-1", "Jane Expert", json.dumps(evidence)),
    ]
    cursor = Cursor([project_rows, graph_rows])
    connection = Connection(cursor)
    repository = SnowflakeIntelligenceRepository(
        factory(connection), database="BLEND_BRAIN", embedding_dimensions=3
    )

    records = repository.load(IntelligenceScope(("project-2", "project-1")))

    assert records[0].technologies == ("Snowflake",)
    assert records[0].experts[0].name == "Jane Expert"
    assert records[0].experts[0].evidence[0].quote == "Jane led"
    assert cursor.executed[0][1] == ("project-1", "project-2", 3)
    assert cursor.executed[1][1] == ("project-1", "project-2")
    assert cursor.closed
    assert connection.closed


@pytest.mark.parametrize(
    "project_rows",
    [
        [("wrong",)],
        [("p", "d", "name", [1.0])],
        [("p", "d", "name", object())],
    ],
)
def test_intelligence_repository_rejects_corrupt_project_rows(
    project_rows: list[tuple[Any, ...]],
) -> None:
    repository = SnowflakeIntelligenceRepository(
        factory(Connection(Cursor([project_rows, []]))),
        database="BLEND_BRAIN",
        embedding_dimensions=3,
    )
    with pytest.raises(IntelligenceCorpusError):
        repository.load(IntelligenceScope(("p",)))


def test_intelligence_repository_rejects_corrupt_graph_rows_and_configuration() -> None:
    repository = SnowflakeIntelligenceRepository(
        factory(Connection(Cursor([[], [("bad",)]]))),
        database="BLEND_BRAIN",
        embedding_dimensions=3,
    )
    with pytest.raises(IntelligenceCorpusError):
        repository.load(IntelligenceScope(("p",)))

    malformed_evidence = SnowflakeIntelligenceRepository(
        factory(
            Connection(
                Cursor(
                    [
                        [("p", "d", "Project", [1.0, 0.0, 0.0])],
                        [("p", "involved_expert", "e", "Expert", ["not-an-object"])],
                    ]
                )
            )
        ),
        database="BLEND_BRAIN",
        embedding_dimensions=3,
    )
    with pytest.raises(IntelligenceCorpusError):
        malformed_evidence.load(IntelligenceScope(("p",)))

    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeIntelligenceRepository(factory(Connection(Cursor())), database="bad-name")
    with pytest.raises(ValueError, match="greater than zero"):
        SnowflakeIntelligenceRepository(
            factory(Connection(Cursor())), database="VALID", embedding_dimensions=0
        )


def test_phase_6_migration_defines_graph_and_audit_tables_without_premature_clustering() -> None:
    migration = (
        Path(__file__).parents[3] / "migrations" / "004_phase_6_organizational_intelligence.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_GRAPH_NODES" in migration
    assert "CREATE TABLE IF NOT EXISTS KNOWLEDGE_GRAPH_EDGES" in migration
    assert "CREATE TABLE IF NOT EXISTS GRAPH_PROJECTION_RUNS" in migration
    assert "CLUSTER BY" not in migration
