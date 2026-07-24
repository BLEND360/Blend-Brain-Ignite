"""Transactional Snowflake persistence for Phase 3 enrichment bundles."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from itertools import batched
from typing import Any, Protocol, Self, cast

import snowflake.connector
from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_enrichment.domain import EnrichmentBundle, PersistenceError

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")
_VECTOR_DIMENSIONS = 3072
_VECTOR_INSERT_BATCH_SIZE = 8


class CursorProtocol(Protocol):
    """Narrow DB-API cursor surface used by the repository."""

    def execute(self, command: str, params: Any = None) -> Self:
        """Execute one statement."""
        ...

    def executemany(self, command: str, params: Any) -> Self:
        """Execute one statement for multiple parameter sets."""
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all rows from the current result."""
        ...

    def close(self) -> None:
        """Close the cursor."""
        ...


class ConnectionProtocol(Protocol):
    """Narrow transactional connection surface used by the repository."""

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
    """Create one isolated Snowflake connection per persistence operation."""

    def __call__(self) -> ConnectionProtocol:
        """Return a connection with autocommit disabled."""
        ...


@dataclass(frozen=True, slots=True)
class SnowflakeConnectionConfig:
    """Validated Snowflake connection parameters."""

    account: str
    user: str
    warehouse: str
    database: str
    schema: str = "KNOWLEDGE_BRAIN"
    role: str | None = None
    password: str | None = None
    private_key_file: str | None = None
    private_key_file_password: str | None = None
    query_tag: str = "blend-knowledge-brain:phase-3"

    def __post_init__(self) -> None:
        for value in (self.database, self.schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        if not self.query_tag.strip():
            raise ValueError("Snowflake query tag cannot be empty")
        if not self.password and not self.private_key_file:
            raise ValueError("Snowflake password or private key is required")


class SnowflakeConnectionFactory:
    """Create short-lived key-pair or password-authenticated connections."""

    def __init__(self, config: SnowflakeConnectionConfig) -> None:
        self._config = config

    def __call__(self) -> ConnectionProtocol:
        """Connect with explicit transaction control and an auditable query tag."""
        parameters: dict[str, object] = {
            "account": self._config.account,
            "user": self._config.user,
            "warehouse": self._config.warehouse,
            "database": self._config.database,
            "schema": self._config.schema,
            "autocommit": False,
            "application": "BlendKnowledgeBrain",
            "session_parameters": {"QUERY_TAG": self._config.query_tag},
        }
        if self._config.role:
            parameters["role"] = self._config.role
        if self._config.password:
            parameters["password"] = self._config.password
        if self._config.private_key_file:
            parameters["private_key_file"] = self._config.private_key_file
        if self._config.private_key_file_password:
            parameters["private_key_file_pwd"] = self._config.private_key_file_password
        return cast("ConnectionProtocol", snowflake.connector.connect(**parameters))


class SnowflakeKnowledgeRepository:
    """Persist document enrichment atomically with idempotent stable keys."""

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

    def persist(self, bundle: EnrichmentBundle) -> None:
        """Replace one document version and its derived data in one transaction."""
        if any(embedding.dimensions != _VECTOR_DIMENSIONS for embedding in bundle.embeddings):
            raise PersistenceError(
                "Embedding dimensions do not match the Snowflake vector schema",
                expected_dimensions=_VECTOR_DIMENSIONS,
            )
        dna_json = self._json(asdict(bundle.project_dna))
        warning_json = self._json([asdict(warning) for warning in bundle.document.warnings])
        try:
            connection = self._connection_factory()
        except SnowflakeError as exception:
            raise self._persistence_error(bundle.run_id, exception) from exception
        cursor: CursorProtocol | None = None
        try:
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            self._upsert_project(cursor, bundle)
            self._upsert_document(cursor, bundle, warning_json)
            self._replace_sections(cursor, bundle)
            self._upsert_dna(cursor, bundle, dna_json)
            self._replace_embeddings(cursor, bundle)
            self._insert_run(cursor, bundle)
            connection.commit()
        except SnowflakeError as exception:
            connection.rollback()
            raise self._persistence_error(bundle.run_id, exception) from exception
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def completed_document_ids(self) -> frozenset[str]:
        """Load document versions that already completed enrichment."""
        try:
            connection = self._connection_factory()
        except SnowflakeError as exception:
            raise self._persistence_error("batch-resume", exception) from exception
        cursor: CursorProtocol | None = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                f"""SELECT DISTINCT document_id
                FROM {self._table("ENRICHMENT_RUNS")}
                WHERE status = %s""",
                ("completed",),
            )
            return frozenset(str(row[0]) for row in cursor.fetchall())
        except SnowflakeError as exception:
            raise self._persistence_error("batch-resume", exception) from exception
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def _upsert_project(self, cursor: CursorProtocol, bundle: EnrichmentBundle) -> None:
        display_name = (
            bundle.project_dna.project_name.value
            if bundle.project_dna.project_name
            else bundle.profile.title or bundle.profile.filename
        )
        cursor.execute(
            f"""MERGE INTO {self._table("PROJECTS")} target
            USING (SELECT %(project_id)s project_id, %(display_name)s display_name,
                          %(dna_id)s dna_id, %(updated_at)s updated_at) source
            ON target.project_id = source.project_id
            WHEN MATCHED THEN UPDATE SET display_name = source.display_name,
                current_dna_id = source.dna_id, updated_at = source.updated_at
            WHEN NOT MATCHED THEN INSERT
                (project_id, display_name, current_dna_id, created_at, updated_at)
                VALUES (source.project_id, source.display_name, source.dna_id,
                        source.updated_at, source.updated_at)""",
            {
                "project_id": bundle.project_id,
                "display_name": display_name,
                "dna_id": bundle.project_dna.dna_id,
                "updated_at": bundle.completed_at,
            },
        )

    def _upsert_document(
        self,
        cursor: CursorProtocol,
        bundle: EnrichmentBundle,
        warnings_json: str,
    ) -> None:
        profile = bundle.profile
        cursor.execute(
            f"""MERGE INTO {self._table("DOCUMENTS")} target
            USING (SELECT %(document_id)s document_id) source
            ON target.document_id = source.document_id
            WHEN MATCHED THEN UPDATE SET updated_at = %(updated_at)s,
                warnings = PARSE_JSON(%(warnings)s)
            WHEN NOT MATCHED THEN INSERT
                (document_id, project_id, source_id, filename, document_format, sha256,
                 size_bytes, title, author, subject, source_created_at, source_modified_at,
                 section_count, character_count, word_count, warnings, created_at, updated_at)
            VALUES (%(document_id)s, %(project_id)s, %(source_id)s, %(filename)s,
                    %(document_format)s, %(sha256)s, %(size_bytes)s, %(title)s, %(author)s,
                    %(subject)s, %(source_created_at)s, %(source_modified_at)s,
                    %(section_count)s, %(character_count)s, %(word_count)s,
                    PARSE_JSON(%(warnings)s), %(updated_at)s, %(updated_at)s)""",
            {
                **asdict(profile),
                "project_id": bundle.project_id,
                "source_created_at": profile.created_at,
                "source_modified_at": profile.modified_at,
                "warnings": warnings_json,
                "updated_at": bundle.completed_at,
            },
        )

    def _replace_sections(self, cursor: CursorProtocol, bundle: EnrichmentBundle) -> None:
        cursor.execute(
            f"DELETE FROM {self._table('DOCUMENT_SECTIONS')} WHERE document_id = %s",
            (bundle.profile.document_id,),
        )
        rows = [
            (
                f"{bundle.profile.document_id}:{section.sequence}",
                bundle.profile.document_id,
                section.sequence,
                section.kind.value,
                section.text,
                section.locator.page_number,
                section.locator.slide_number,
                section.locator.heading,
                bundle.completed_at,
            )
            for section in bundle.document.sections
        ]
        if rows:
            cursor.executemany(
                f"""INSERT INTO {self._table("DOCUMENT_SECTIONS")}
                (section_id, document_id, sequence, section_kind, text, page_number,
                 slide_number, heading, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                rows,
            )

    def _upsert_dna(
        self,
        cursor: CursorProtocol,
        bundle: EnrichmentBundle,
        dna_json: str,
    ) -> None:
        dna = bundle.project_dna
        cursor.execute(
            f"""MERGE INTO {self._table("PROJECT_DNA")} target
            USING (SELECT %(dna_id)s dna_id) source ON target.dna_id = source.dna_id
            WHEN MATCHED THEN UPDATE SET dna_json = PARSE_JSON(%(dna_json)s),
                generated_at = %(generated_at)s
            WHEN NOT MATCHED THEN INSERT
                (dna_id, project_id, document_id, version, model, prompt_version,
                 dna_json, generated_at)
            VALUES (%(dna_id)s, %(project_id)s, %(document_id)s, %(version)s,
                    %(model)s, %(prompt_version)s, PARSE_JSON(%(dna_json)s),
                    %(generated_at)s)""",
            {
                "dna_id": dna.dna_id,
                "project_id": dna.project_id,
                "document_id": dna.document_id,
                "version": dna.version,
                "model": dna.model,
                "prompt_version": dna.prompt_version,
                "dna_json": dna_json,
                "generated_at": dna.generated_at,
            },
        )

    def _replace_embeddings(self, cursor: CursorProtocol, bundle: EnrichmentBundle) -> None:
        cursor.execute(
            f"DELETE FROM {self._table('EMBEDDINGS')} WHERE document_id = %s",
            (bundle.profile.document_id,),
        )
        rows = [
            (
                item.embedding_id,
                item.project_id,
                item.document_id,
                item.target_type.value,
                item.target_id,
                item.section_sequence,
                item.content_sha256,
                item.model,
                item.dimensions,
                json.dumps(item.vector, separators=(",", ":")),
                item.created_at,
            )
            for item in bundle.embeddings
        ]
        row_template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        for row_batch in batched(rows, _VECTOR_INSERT_BATCH_SIZE, strict=False):
            values_clause = ", ".join(row_template for _row in row_batch)
            parameters = tuple(value for row in row_batch for value in row)
            cursor.execute(
                f"""INSERT INTO {self._table("EMBEDDINGS")}
                (embedding_id, project_id, document_id, target_type, target_id,
                 section_sequence, content_sha256, model, dimensions, vector, created_at)
                SELECT column1, column2, column3, column4, column5, column6, column7,
                       column8, column9,
                       PARSE_JSON(column10)::VECTOR(FLOAT, {_VECTOR_DIMENSIONS}), column11
                FROM VALUES {values_clause}""",
                parameters,
            )

    def _insert_run(self, cursor: CursorProtocol, bundle: EnrichmentBundle) -> None:
        cursor.execute(
            f"""INSERT INTO {self._table("ENRICHMENT_RUNS")}
            (run_id, project_id, document_id, status, embedding_count, completed_at)
            VALUES (%s, %s, %s, 'completed', %s, %s)""",
            (
                bundle.run_id,
                bundle.project_id,
                bundle.profile.document_id,
                len(bundle.embeddings),
                bundle.completed_at,
            ),
        )

    def _table(self, table: str) -> str:
        return f'{self._namespace}."{table}"'

    @staticmethod
    def _persistence_error(run_id: str, exception: SnowflakeError) -> PersistenceError:
        return PersistenceError(
            "Snowflake transaction failed",
            run_id=run_id,
            sqlstate=exception.sqlstate,
            errno=exception.errno,
        )

    @staticmethod
    def _json(value: object) -> str:
        def encode(item: object) -> str:
            if isinstance(item, datetime):
                return item.isoformat()
            if isinstance(item, Enum):
                return str(item.value)
            raise TypeError(f"Cannot serialize {type(item).__name__}")

        return json.dumps(value, default=encode, separators=(",", ":"), sort_keys=True)
