"""Snowflake evidence loading and business-artifact persistence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any, Protocol, Self
from uuid import NAMESPACE_URL, uuid5

from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.business_artifacts.domain import (
    ArtifactCitation,
    ArtifactExport,
    ArtifactKind,
    ArtifactPersistenceError,
    ArtifactScope,
    ArtifactSection,
    ArtifactSource,
    ArtifactSourceError,
    ArtifactSourceKind,
    ArtifactStatement,
    ArtifactStatus,
    BusinessArtifact,
    BusinessArtifactError,
    OnePagerBrief,
    ProjectOnePagerArtifact,
    ProposalArtifact,
    ProposalBrief,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")


class CursorProtocol(Protocol):
    """Narrow DB-API cursor surface used by Phase 8."""

    def execute(self, command: str, params: Any = None) -> Self:
        """Execute one statement."""
        ...

    def executemany(self, command: str, params: Any) -> Self:
        """Execute a statement for multiple rows."""
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
        """Return one row."""
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Return a bounded result set."""
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
    """Create one isolated connection per operation."""

    def __call__(self) -> ConnectionProtocol:
        """Return a connection."""
        ...


class SnowflakeBusinessArtifactRepository:
    """Persist artifacts atomically and load only authorized current sources."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        database: str,
        schema: str = "KNOWLEDGE_BRAIN",
        max_sections_per_project: int = 100,
    ) -> None:
        for value in (database, schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        if max_sections_per_project <= 0:
            raise ValueError("max_sections_per_project must be greater than zero")
        self._connection_factory = connection_factory
        self._namespace = f'"{database.upper()}"."{schema.upper()}"'
        self._max_sections_per_project = max_sections_per_project

    def load_project_sources(self, project_ids: tuple[str, ...]) -> tuple[ArtifactSource, ...]:
        """Load bounded sections behind each project's current DNA document."""
        if not project_ids:
            raise ValueError("project_ids cannot be empty")
        placeholders = ", ".join("%s" for _ in project_ids)
        rows = self._fetch_all(
            f"""SELECT project_id, document_id, sequence, filename, text
            FROM (
                SELECT p.project_id, dna.document_id, section.sequence, document.filename,
                       section.text,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.project_id ORDER BY section.sequence
                       ) source_rank
                FROM {self._table("PROJECTS")} p
                INNER JOIN {self._table("PROJECT_DNA")} dna
                    ON dna.dna_id = p.current_dna_id
                INNER JOIN {self._table("DOCUMENTS")} document
                    ON document.document_id = dna.document_id
                INNER JOIN {self._table("DOCUMENT_SECTIONS")} section
                    ON section.document_id = dna.document_id
                WHERE p.project_id IN ({placeholders})
            )
            WHERE source_rank <= %s
            ORDER BY project_id, sequence""",
            (*project_ids, self._max_sections_per_project),
        )
        sources: list[ArtifactSource] = []
        try:
            for index, row in enumerate(rows, 1):
                sources.append(self._source(row, index))
        except (TypeError, ValueError) as exception:
            raise ArtifactSourceError("Snowflake returned corrupt artifact sources") from exception
        return tuple(sources)

    def find_by_request(
        self,
        request_id: str,
        kind: ArtifactKind,
        created_by: str,
        project_ids: tuple[str, ...],
    ) -> BusinessArtifact | None:
        """Find the result for an actor-scoped idempotency request."""
        row = self._fetch_one(
            f"""SELECT artifact_id, request_id, source_project_ids, brief, title, subtitle,
                       content, model, prompt_version, status, content_sha256,
                       created_by, created_at
                FROM {self._table_for(kind)}
                WHERE request_id = %s AND created_by = %s
                    AND source_project_ids = PARSE_JSON(%s)""",
            (request_id, created_by, self._json(project_ids)),
        )
        return self._map_artifact(row, kind) if row is not None else None

    def persist(self, artifact: BusinessArtifact, sources: tuple[ArtifactSource, ...]) -> None:
        """Insert one immutable artifact and its citation projection atomically."""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            table = self._table_for(self._kind(artifact))
            cursor.execute(
                f"""MERGE INTO {table} target
                USING (SELECT %s artifact_id, %s request_id, PARSE_JSON(%s) source_project_ids,
                              PARSE_JSON(%s) brief, %s title, %s subtitle,
                              PARSE_JSON(%s) content, %s model, %s prompt_version, %s status,
                              %s content_sha256, %s created_by, %s created_at) source
                ON target.artifact_id = source.artifact_id
                WHEN MATCHED THEN UPDATE SET artifact_id = target.artifact_id
                WHEN NOT MATCHED THEN INSERT
                    (artifact_id, request_id, source_project_ids, brief, title, subtitle,
                     content, model, prompt_version, status, content_sha256, created_by, created_at)
                    VALUES (source.artifact_id, source.request_id, source.source_project_ids,
                            source.brief, source.title, source.subtitle, source.content,
                            source.model, source.prompt_version, source.status,
                            source.content_sha256, source.created_by, source.created_at)""",
                (
                    artifact.artifact_id,
                    artifact.request_id,
                    self._json(artifact.source_project_ids),
                    self._json(asdict(artifact.brief)),
                    artifact.title,
                    artifact.subtitle,
                    self._json([asdict(section) for section in artifact.sections]),
                    artifact.model,
                    artifact.prompt_version,
                    artifact.status.value,
                    artifact.content_sha256,
                    artifact.created_by,
                    artifact.created_at,
                ),
            )
            cursor.execute(
                f"SELECT content_sha256 FROM {table} WHERE artifact_id = %s",
                (artifact.artifact_id,),
            )
            persisted = cursor.fetchone()
            if (
                persisted is None
                or len(persisted) != 1
                or str(persisted[0]) != artifact.content_sha256
            ):
                raise ArtifactPersistenceError(
                    "Idempotency identity already contains different artifact content"
                )
            cursor.execute(
                f"DELETE FROM {self._table('ARTIFACT_CITATIONS')} WHERE artifact_id = %s",
                (artifact.artifact_id,),
            )
            self._insert_citations(cursor, artifact, sources)
            connection.commit()
        except BusinessArtifactError:
            if connection is not None:
                connection.rollback()
            raise
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise self._error("Snowflake artifact transaction failed", exception) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def get_artifact(
        self, artifact_id: str, kind: ArtifactKind, scope: ArtifactScope
    ) -> BusinessArtifact | None:
        """Load only artifacts whose complete source set is within the allowlist."""
        row = self._fetch_one(
            f"""SELECT artifact_id, request_id, source_project_ids, brief, title, subtitle,
                       content, model, prompt_version, status, content_sha256,
                       created_by, created_at
                FROM {self._table_for(kind)}
                WHERE artifact_id = %s
                  AND ARRAY_SIZE(ARRAY_EXCEPT(source_project_ids::ARRAY,
                      PARSE_JSON(%s)::ARRAY)) = 0""",
            (artifact_id, self._json(scope.project_ids)),
        )
        return self._map_artifact(row, kind) if row is not None else None

    def record_export(self, export: ArtifactExport) -> None:
        """Insert immutable private-object metadata."""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                f"""INSERT INTO {self._table("ARTIFACT_EXPORTS")}
                (export_id, artifact_id, artifact_kind, storage_location, object_key,
                 content_type, size_bytes, sha256, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    export.export_id,
                    export.artifact_id,
                    export.artifact_kind.value,
                    export.storage_location,
                    export.object_key,
                    export.content_type,
                    export.size_bytes,
                    export.sha256,
                    export.created_by,
                    export.created_at,
                ),
            )
            connection.commit()
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise self._error(
                "Snowflake export metadata transaction failed", exception
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _insert_citations(
        self,
        cursor: CursorProtocol,
        artifact: BusinessArtifact,
        sources: tuple[ArtifactSource, ...],
    ) -> None:
        source_map = {source.source_id: source for source in sources}
        rows: list[tuple[object, ...]] = []
        for section_index, section in enumerate(artifact.sections):
            for statement_index, statement in enumerate(section.statements):
                for citation_index, citation in enumerate(statement.citations):
                    source = source_map.get(citation.source_id)
                    if source is None:
                        raise ArtifactSourceError(
                            "Artifact citation source disappeared before persistence"
                        )
                    citation_id = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"{artifact.artifact_id}:{section_index}:{statement_index}:"
                            f"{citation_index}",
                        )
                    )
                    rows.append(
                        (
                            citation_id,
                            artifact.artifact_id,
                            self._kind(artifact).value,
                            section.key,
                            statement_index,
                            statement.text,
                            source.source_id,
                            source.kind.value,
                            source.project_id,
                            source.document_id,
                            source.section_sequence,
                            source.filename,
                            citation.quote,
                            artifact.created_at,
                        )
                    )
        if rows:
            cursor.executemany(
                f"""INSERT INTO {self._table("ARTIFACT_CITATIONS")}
                (citation_id, artifact_id, artifact_kind, section_key, statement_sequence,
                 statement_text, source_id, source_kind, project_id, document_id,
                 section_sequence, filename, quote, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                rows,
            )

    def _map_artifact(self, row: tuple[Any, ...], kind: ArtifactKind) -> BusinessArtifact:
        if len(row) != 13:
            raise ArtifactPersistenceError("Snowflake returned an invalid artifact row")
        try:
            project_ids_raw = self._json_list(row[2], "source_project_ids")
            brief_raw = self._json_dict(row[3], "brief")
            content_raw = self._json_list(row[6], "content")
            sections = tuple(self._section(item) for item in content_raw)
            common = {
                "artifact_id": str(row[0]),
                "request_id": str(row[1]),
                "source_project_ids": tuple(str(item) for item in project_ids_raw),
                "title": str(row[4]),
                "subtitle": str(row[5]) if row[5] is not None else None,
                "sections": sections,
                "model": str(row[7]),
                "prompt_version": str(row[8]),
                "status": ArtifactStatus(str(row[9])),
                "content_sha256": str(row[10]),
                "created_by": str(row[11]),
                "created_at": row[12],
            }
            if kind is ArtifactKind.PROPOSAL:
                return ProposalArtifact(
                    **common,
                    brief=ProposalBrief(
                        client_name=str(brief_raw["client_name"]),
                        audience=str(brief_raw["audience"]),
                        opportunity=str(brief_raw["opportunity"]),
                        objectives=self._string_tuple(brief_raw["objectives"], "objectives"),
                        constraints=self._string_tuple(brief_raw["constraints"], "constraints"),
                    ),
                )
            return ProjectOnePagerArtifact(
                **common,
                brief=OnePagerBrief(
                    project_id=str(brief_raw["project_id"]),
                    audience=str(brief_raw["audience"]),
                ),
            )
        except (KeyError, TypeError, ValueError) as exception:
            raise ArtifactPersistenceError(
                "Snowflake returned corrupt artifact data"
            ) from exception

    @staticmethod
    def _section(raw: object) -> ArtifactSection:
        if not isinstance(raw, dict) or not isinstance(raw.get("statements"), list):
            raise TypeError("Artifact section is invalid")
        statements: list[ArtifactStatement] = []
        for statement_raw in raw["statements"]:
            if not isinstance(statement_raw, dict) or not isinstance(
                statement_raw.get("citations"), list
            ):
                raise TypeError("Artifact statement is invalid")
            citations = tuple(
                ArtifactCitation(
                    str(item["source_id"]),
                    str(item["quote"]),
                    source_kind=(
                        ArtifactSourceKind(str(item["source_kind"]))
                        if item.get("source_kind") is not None
                        else None
                    ),
                    project_id=(str(item["project_id"]) if item.get("project_id") else None),
                    document_id=(str(item["document_id"]) if item.get("document_id") else None),
                    section_sequence=(
                        int(item["section_sequence"])
                        if item.get("section_sequence") is not None
                        else None
                    ),
                    filename=(str(item["filename"]) if item.get("filename") else None),
                )
                for item in statement_raw["citations"]
                if isinstance(item, dict)
            )
            if len(citations) != len(statement_raw["citations"]):
                raise TypeError("Artifact citation is invalid")
            statements.append(ArtifactStatement(str(statement_raw["text"]), citations))
        return ArtifactSection(str(raw["key"]), str(raw["heading"]), tuple(statements))

    def _fetch_one(self, command: str, params: tuple[object, ...]) -> tuple[Any, ...] | None:
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(command, params)
            return cursor.fetchone()
        except SnowflakeError as exception:
            raise self._error("Snowflake artifact read failed", exception) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @staticmethod
    def _source(row: tuple[Any, ...], index: int) -> ArtifactSource:
        if len(row) != 5:
            raise ValueError("Unexpected artifact source row shape")
        return ArtifactSource(
            source_id=f"P{index}",
            kind=ArtifactSourceKind.PROJECT_DOCUMENT,
            project_id=str(row[0]),
            document_id=str(row[1]),
            section_sequence=int(row[2]),
            filename=str(row[3]),
            text=str(row[4]),
        )

    @classmethod
    def _json_list(cls, value: object, field: str) -> list[object]:
        try:
            parsed = cls._parse_json(value)
        except (TypeError, ValueError) as exception:
            raise ArtifactPersistenceError(f"{field} contains invalid JSON") from exception
        if not isinstance(parsed, list):
            raise ArtifactPersistenceError(f"{field} must be an array")
        return parsed

    @classmethod
    def _json_dict(cls, value: object, field: str) -> dict[str, object]:
        try:
            parsed = cls._parse_json(value)
        except (TypeError, ValueError) as exception:
            raise ArtifactPersistenceError(f"{field} contains invalid JSON") from exception
        if not isinstance(parsed, dict):
            raise ArtifactPersistenceError(f"{field} must be an object")
        return parsed

    @staticmethod
    def _string_tuple(value: object, field: str) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise ArtifactPersistenceError(f"{field} must be an array")
        return tuple(str(item) for item in value)

    def _fetch_all(self, command: str, params: tuple[object, ...]) -> list[tuple[Any, ...]]:
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(command, params)
            return cursor.fetchall()
        except SnowflakeError as exception:
            raise ArtifactSourceError(
                "Snowflake artifact source load failed",
                sqlstate=exception.sqlstate,
                errno=exception.errno,
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _table(self, table: str) -> str:
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError(f"Unsafe Snowflake table identifier: {table}")
        return f'{self._namespace}."{table}"'

    def _table_for(self, kind: ArtifactKind) -> str:
        return self._table("PROPOSALS" if kind is ArtifactKind.PROPOSAL else "PROJECT_ONE_PAGERS")

    @staticmethod
    def _kind(artifact: BusinessArtifact) -> ArtifactKind:
        return (
            ArtifactKind.PROPOSAL
            if isinstance(artifact, ProposalArtifact)
            else ArtifactKind.PROJECT_ONE_PAGER
        )

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _parse_json(value: object) -> object:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _error(message: str, exception: SnowflakeError) -> ArtifactPersistenceError:
        return ArtifactPersistenceError(
            message,
            sqlstate=exception.sqlstate,
            errno=exception.errno,
        )
