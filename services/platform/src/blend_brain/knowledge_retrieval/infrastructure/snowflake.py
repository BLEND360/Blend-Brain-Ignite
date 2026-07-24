"""Read-only Snowflake corpus adapter with mandatory project scoping."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, Self

from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_retrieval.domain import (
    CorpusLoadError,
    IndexedSection,
    RetrievalScope,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")


class ReadCursorProtocol(Protocol):
    """Narrow read-only DB-API cursor surface."""

    def execute(self, command: str, params: Any = None) -> Self:
        """Execute one parameterized statement."""
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all rows from the bounded scoped query."""
        ...

    def close(self) -> None:
        """Close the cursor."""
        ...


class ReadConnectionProtocol(Protocol):
    """Narrow connection surface required by corpus reads."""

    def cursor(self) -> ReadCursorProtocol:
        """Create a cursor."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


class ReadConnectionFactory(Protocol):
    """Create one isolated Snowflake connection per load."""

    def __call__(self) -> ReadConnectionProtocol:
        """Return a connection."""
        ...


class SnowflakeRetrievalCorpusRepository:
    """Load section text and vectors from the durable Phase 3 schema."""

    def __init__(
        self,
        connection_factory: ReadConnectionFactory,
        *,
        database: str,
        schema: str = "KNOWLEDGE_BRAIN",
        embedding_dimensions: int = 3072,
    ) -> None:
        for value in (database, schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        if embedding_dimensions <= 0:
            raise ValueError("embedding_dimensions must be greater than zero")
        self._connection_factory = connection_factory
        self._namespace = f'"{database.upper()}"."{schema.upper()}"'
        self._embedding_dimensions = embedding_dimensions

    def load(self, scope: RetrievalScope) -> tuple[IndexedSection, ...]:
        """Load only allowlisted projects before any index is constructed."""
        placeholders = ", ".join("%s" for _ in scope.project_ids)
        command = f"""SELECT s.section_id, d.project_id, d.document_id, d.filename,
                   s.sequence, s.section_kind, s.text, s.page_number,
                   s.slide_number, s.heading, e.vector::ARRAY
            FROM {self._table("DOCUMENT_SECTIONS")} s
            INNER JOIN {self._table("DOCUMENTS")} d
                ON d.document_id = s.document_id
            INNER JOIN {self._table("EMBEDDINGS")} e
                ON e.document_id = s.document_id
                AND e.section_sequence = s.sequence
                AND e.target_type = 'document_section'
            WHERE d.project_id IN ({placeholders})
                AND e.dimensions = %s
            ORDER BY d.project_id, d.document_id, s.sequence"""
        connection: ReadConnectionProtocol | None = None
        cursor: ReadCursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(command, (*scope.project_ids, self._embedding_dimensions))
            rows = cursor.fetchall()
            return tuple(self._row(row) for row in rows)
        except (SnowflakeError, ValueError, TypeError) as exception:
            raise CorpusLoadError(
                "Snowflake retrieval corpus load failed",
                project_count=len(scope.project_ids),
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _row(self, row: tuple[Any, ...]) -> IndexedSection:
        if len(row) != 11:
            raise ValueError("Snowflake returned an unexpected corpus row shape")
        raw_vector = row[10]
        if isinstance(raw_vector, str):
            raw_vector = json.loads(raw_vector)
        if not isinstance(raw_vector, (list, tuple)):
            raise TypeError("Snowflake vector must be an array")
        vector = tuple(float(value) for value in raw_vector)
        if len(vector) != self._embedding_dimensions:
            raise ValueError("Snowflake vector dimensions do not match configuration")
        return IndexedSection(
            section_id=str(row[0]),
            project_id=str(row[1]),
            document_id=str(row[2]),
            filename=str(row[3]),
            sequence=int(row[4]),
            kind=str(row[5]),
            text=str(row[6]),
            page_number=int(row[7]) if row[7] is not None else None,
            slide_number=int(row[8]) if row[8] is not None else None,
            heading=str(row[9]) if row[9] is not None else None,
            embedding=vector,
        )

    def _table(self, name: str) -> str:
        if not _IDENTIFIER.fullmatch(name):
            raise ValueError(f"Unsafe Snowflake table identifier: {name}")
        return f'{self._namespace}."{name}"'
