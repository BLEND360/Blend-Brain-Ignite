"""Snowflake-backed authorized knowledge catalog read models."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Protocol, Self

from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_catalog.domain import (
    CatalogDocument,
    CatalogProject,
    DashboardSnapshot,
    IndustryCount,
)
from blend_brain.knowledge_enrichment.infrastructure.project_dna_mapper import (
    project_dna_from_json,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")


class CursorProtocol(Protocol):
    def execute(self, command: str, params: Any = None) -> Self: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def close(self) -> None: ...


class ConnectionProtocol(Protocol):
    def cursor(self) -> CursorProtocol: ...
    def close(self) -> None: ...


class ConnectionFactory(Protocol):
    def __call__(self) -> ConnectionProtocol: ...


class SnowflakeKnowledgeCatalogRepository:
    """Build UI read models using parameter-bound project scopes."""

    def __init__(
        self, connection_factory: ConnectionFactory, *, database: str, schema: str
    ) -> None:
        for value in (database, schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        self._connection_factory = connection_factory
        self._namespace = f'"{database.upper()}"."{schema.upper()}"'

    def all_project_ids(self) -> tuple[str, ...]:
        rows = self._fetch(f"SELECT project_id FROM {self._table('PROJECTS')} ORDER BY project_id")
        return tuple(str(row[0]) for row in rows)

    def dashboard(self, project_ids: tuple[str, ...]) -> DashboardSnapshot:
        projects = self._load_projects(project_ids, include_details=False)
        placeholders = self._placeholders(project_ids)
        document_rows = self._fetch(
            f"SELECT COUNT(*) FROM {self._table('DOCUMENTS')} WHERE project_id IN ({placeholders})",
            project_ids,
        )
        experts = {
            claim.value.casefold()
            for project in projects
            if project.dna is not None
            for claim in project.dna.experts
        }
        industry_counts = Counter(
            project.dna.industry.value
            for project in projects
            if project.dna is not None and project.dna.industry is not None
        )
        classified = sum(
            project.dna is not None and project.dna.summary is not None for project in projects
        )
        recent = tuple(sorted(projects, key=lambda item: item.updated_at, reverse=True)[:8])
        updated_at = max((project.updated_at for project in projects), default=datetime.now(UTC))
        return DashboardSnapshot(
            total_projects=len(projects),
            indexed_documents=int(document_rows[0][0]),
            identified_experts=len(experts),
            knowledge_coverage=classified / len(projects) if projects else 0.0,
            recent_projects=recent,
            top_industries=tuple(
                IndustryCount(name, count)
                for name, count in sorted(
                    industry_counts.items(), key=lambda item: (-item[1], item[0].casefold())
                )[:10]
            ),
            updated_at=updated_at,
        )

    def project(self, project_id: str, project_ids: tuple[str, ...]) -> CatalogProject | None:
        if project_id not in project_ids:
            return None
        projects = self._load_projects((project_id,), include_details=True)
        return projects[0] if projects else None

    def projects(
        self, requested_ids: tuple[str, ...], project_ids: tuple[str, ...]
    ) -> tuple[CatalogProject, ...]:
        allowed = set(project_ids)
        bounded = tuple(project_id for project_id in requested_ids if project_id in allowed)
        return self._load_projects(bounded, include_details=False) if bounded else ()

    def _load_projects(
        self, project_ids: tuple[str, ...], *, include_details: bool
    ) -> tuple[CatalogProject, ...]:
        placeholders = self._placeholders(project_ids)
        rows = self._fetch(
            f"""SELECT p.project_id, p.display_name, p.updated_at, dna.dna_json,
                       (SELECT COUNT(*) FROM {self._table("DOCUMENTS")} document_count
                        WHERE document_count.project_id = p.project_id)
            FROM {self._table("PROJECTS")} p
            LEFT JOIN {self._table("PROJECT_DNA")} dna ON dna.dna_id = p.current_dna_id
            WHERE p.project_id IN ({placeholders})
            ORDER BY p.project_id""",
            project_ids,
        )
        documents: dict[str, list[CatalogDocument]] = {}
        locations: dict[str, list[tuple[int, int | None, int | None, str | None]]] = {}
        if include_details:
            for row in self._fetch(
                f"""SELECT project_id, document_id, filename, document_format,
                           section_count, updated_at
                FROM {self._table("DOCUMENTS")}
                WHERE project_id IN ({placeholders})
                ORDER BY filename""",
                project_ids,
            ):
                documents.setdefault(str(row[0]), []).append(
                    CatalogDocument(
                        document_id=str(row[1]),
                        filename=str(row[2]),
                        document_format=str(row[3]),
                        section_count=int(row[4]),
                        updated_at=row[5],
                    )
                )
            dna_documents = tuple(
                project_dna_from_json(row[3]).document_id for row in rows if row[3] is not None
            )
            if dna_documents:
                dna_placeholders = self._placeholders(dna_documents)
                for row in self._fetch(
                    f"""SELECT document_id, sequence, page_number, slide_number, heading
                    FROM {self._table("DOCUMENT_SECTIONS")}
                    WHERE document_id IN ({dna_placeholders}) ORDER BY document_id, sequence""",
                    dna_documents,
                ):
                    locations.setdefault(str(row[0]), []).append(
                        (
                            int(row[1]),
                            int(row[2]) if row[2] is not None else None,
                            int(row[3]) if row[3] is not None else None,
                            str(row[4]) if row[4] is not None else None,
                        )
                    )
        result: list[CatalogProject] = []
        for row in rows:
            dna = project_dna_from_json(row[3]) if row[3] is not None else None
            project_id = str(row[0])
            result.append(
                CatalogProject(
                    project_id=project_id,
                    display_name=str(row[1]),
                    updated_at=row[2],
                    dna=dna,
                    document_count=int(row[4]),
                    documents=tuple(documents.get(project_id, ())),
                    section_locations=(
                        tuple(locations.get(dna.document_id, ())) if dna is not None else ()
                    ),
                )
            )
        return tuple(result)

    def _fetch(self, command: str, params: Any = None) -> list[tuple[Any, ...]]:
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(command, params)
            return cursor.fetchall()
        except SnowflakeError as exception:
            raise RuntimeError("Snowflake knowledge catalog query failed") from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @staticmethod
    def _placeholders(values: tuple[str, ...]) -> str:
        if not values:
            raise ValueError("A knowledge catalog query requires a non-empty scope")
        return ", ".join("%s" for _ in values)

    def _table(self, table: str) -> str:
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError(f"Unsafe Snowflake table identifier: {table}")
        return f'{self._namespace}."{table}"'
