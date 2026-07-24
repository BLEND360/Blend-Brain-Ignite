"""Snowflake knowledge catalog mapping and scoping tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Self

import pytest
from tests.unit.knowledge_enrichment.helpers import dna

from blend_brain.knowledge_catalog.infrastructure import SnowflakeKnowledgeCatalogRepository

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)


class Cursor:
    def __init__(self, results: list[list[tuple[Any, ...]]]) -> None:
        self.results = results
        self.current: list[tuple[Any, ...]] = []
        self.closed = False
        self.commands: list[tuple[str, Any]] = []

    def execute(self, command: str, params: Any = None) -> Self:
        self.commands.append((command, params))
        self.current = self.results.pop(0)
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.current

    def close(self) -> None:
        self.closed = True


class Connection:
    def __init__(self, cursor: Cursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self) -> Cursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self, results: list[list[tuple[Any, ...]]]) -> None:
        self.cursor = Cursor(results)
        self.connections: list[Connection] = []

    def __call__(self) -> Connection:
        connection = Connection(self.cursor)
        self.connections.append(connection)
        return connection


def project_row() -> tuple[Any, ...]:
    persisted = json.loads(json.dumps(asdict(dna()), default=str))
    return ("project-1", "Retail Forecasting", NOW, persisted, 1)


def test_maps_dashboard_metrics_and_explicit_project_details() -> None:
    factory = Factory(
        [
            [("project-1",)],
            [project_row()],
            [(1,)],
            [project_row()],
            [("project-1", "document-id", "project.md", "markdown", 2, NOW)],
            [("document-id", 1, None, None, "Overview")],
        ]
    )
    repository = SnowflakeKnowledgeCatalogRepository(
        factory, database="CLARITY_DB", schema="RETAIL"
    )

    assert repository.all_project_ids() == ("project-1",)
    dashboard = repository.dashboard(("project-1",))
    project = repository.project("project-1", ("project-1",))

    assert dashboard.total_projects == 1
    assert dashboard.indexed_documents == 1
    assert dashboard.knowledge_coverage == 1.0
    assert dashboard.top_industries == ()
    assert project is not None
    assert project.documents[0].filename == "project.md"
    assert project.section_locations[0][3] == "Overview"
    assert all(connection.closed for connection in factory.connections)
    assert factory.cursor.closed


def test_scopes_summary_queries_and_handles_empty_results() -> None:
    factory = Factory([[project_row()], [], [(0,)]])
    repository = SnowflakeKnowledgeCatalogRepository(
        factory, database="CLARITY_DB", schema="RETAIL"
    )

    assert repository.projects(("project-1", "secret"), ("project-1",))[0].project_id == "project-1"
    assert repository.project("secret", ("project-1",)) is None
    assert repository.projects(("secret",), ("project-1",)) == ()
    assert repository.dashboard(("project-1",)).total_projects == 0


def test_rejects_unsafe_identifiers_and_empty_query_scope() -> None:
    with pytest.raises(ValueError, match="Unsafe Snowflake identifier"):
        SnowflakeKnowledgeCatalogRepository(Factory([]), database="bad-name", schema="RETAIL")
    repository = SnowflakeKnowledgeCatalogRepository(
        Factory([]), database="CLARITY_DB", schema="RETAIL"
    )
    with pytest.raises(ValueError, match="non-empty scope"):
        repository.dashboard(())
