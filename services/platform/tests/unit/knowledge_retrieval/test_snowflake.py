"""Scoped Snowflake corpus repository tests."""

from __future__ import annotations

import json
from typing import Any, Self, cast

import pytest
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_retrieval.domain import CorpusLoadError, RetrievalScope
from blend_brain.knowledge_retrieval.infrastructure.snowflake import (
    ReadConnectionProtocol,
    SnowflakeRetrievalCorpusRepository,
)


class Cursor:
    """Read cursor test double."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.command = ""
        self.params: Any = None
        self.closed = False
        self.error: SnowflakeError | None = None

    def execute(self, command: str, params: Any = None) -> Self:
        if self.error:
            raise self.error
        self.command = command
        self.params = params
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class Connection:
    """Read connection test double."""

    def __init__(self, cursor: Cursor) -> None:
        self.test_cursor = cursor
        self.closed = False

    def cursor(self) -> Cursor:
        return self.test_cursor

    def close(self) -> None:
        self.closed = True


def repository(connection: Connection) -> SnowflakeRetrievalCorpusRepository:
    """Create a three-dimensional test repository."""
    return SnowflakeRetrievalCorpusRepository(
        lambda: cast("ReadConnectionProtocol", connection),
        database="BLEND_BRAIN",
        embedding_dimensions=3,
    )


def row(vector: object = (1.0, 2.0, 3.0)) -> tuple[Any, ...]:
    """Return one representative Snowflake row."""
    return (
        "section-1",
        "project-1",
        "document-1",
        "project.pdf",
        2,
        "body",
        "text",
        4,
        None,
        "Outcome",
        vector,
    )


def test_repository_binds_scope_and_maps_citation_metadata() -> None:
    cursor = Cursor([row(json.dumps([1.0, 2.0, 3.0]))])
    connection = Connection(cursor)

    sections = repository(connection).load(RetrievalScope(("project-2", "project-1")))

    assert sections[0].page_number == 4
    assert sections[0].embedding == (1.0, 2.0, 3.0)
    assert cursor.params == ("project-1", "project-2", 3)
    assert "IN (%s, %s)" in cursor.command
    assert "target_type = 'document_section'" in cursor.command
    assert cursor.closed
    assert connection.closed


@pytest.mark.parametrize("invalid_vector", [[1.0], "not-json", object()])
def test_repository_translates_corrupt_vector_data(invalid_vector: object) -> None:
    with pytest.raises(CorpusLoadError):
        repository(Connection(Cursor([row(invalid_vector)]))).load(RetrievalScope(("p",)))


def test_repository_translates_snowflake_errors_and_validates_config() -> None:
    cursor = Cursor([])
    cursor.error = SnowflakeError(msg="failed", errno=1)
    connection = Connection(cursor)
    with pytest.raises(CorpusLoadError):
        repository(connection).load(RetrievalScope(("p",)))
    assert cursor.closed
    assert connection.closed

    with pytest.raises(ValueError, match="Unsafe"):
        SnowflakeRetrievalCorpusRepository(
            lambda: cast("ReadConnectionProtocol", connection), database="bad-name"
        )
    with pytest.raises(ValueError, match="greater than zero"):
        SnowflakeRetrievalCorpusRepository(
            lambda: cast("ReadConnectionProtocol", connection),
            database="VALID",
            embedding_dimensions=0,
        )
