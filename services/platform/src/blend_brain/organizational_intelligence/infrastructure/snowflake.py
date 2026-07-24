"""Snowflake graph persistence and scoped intelligence corpus loading."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from itertools import batched
from typing import TYPE_CHECKING, Any, Protocol, Self

from snowflake.connector.errors import Error as SnowflakeError

from blend_brain.knowledge_enrichment.infrastructure.project_dna_mapper import (
    project_dna_from_json,
)
from blend_brain.organizational_intelligence.domain import (
    ExpertAssociation,
    GraphEvidence,
    GraphPersistenceError,
    IntelligenceCorpusError,
    IntelligenceScope,
    KnowledgeGraphSnapshot,
    ProjectIntelligenceRecord,
    RelationshipType,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$]*$")
_NODE_UPSERT_BATCH_SIZE = 64
_EDGE_INSERT_BATCH_SIZE = 32
_RUN_UPSERT_BATCH_SIZE = 64

if TYPE_CHECKING:
    from blend_brain.knowledge_enrichment.domain import ProjectDNA


class CursorProtocol(Protocol):
    """Narrow DB-API cursor surface used by Phase 6 repositories."""

    def execute(self, command: str, params: Any = None) -> Self:
        """Execute one statement."""
        ...

    def executemany(self, command: str, params: Any) -> Self:
        """Execute a statement for multiple parameter sets."""
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Return all bounded scoped rows."""
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
    """Create one isolated Snowflake connection per operation."""

    def __call__(self) -> ConnectionProtocol:
        """Return a connection."""
        ...


class _SnowflakeRepository:
    def __init__(
        self, connection_factory: ConnectionFactory, *, database: str, schema: str
    ) -> None:
        for value in (database, schema):
            if not _IDENTIFIER.fullmatch(value):
                raise ValueError(f"Unsafe Snowflake identifier: {value}")
        self._connection_factory = connection_factory
        self._namespace = f'"{database.upper()}"."{schema.upper()}"'

    def _table(self, table: str) -> str:
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError(f"Unsafe Snowflake table identifier: {table}")
        return f'{self._namespace}."{table}"'


class SnowflakeKnowledgeGraphRepository(_SnowflakeRepository):
    """Atomically persist one idempotent graph projection."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        database: str,
        schema: str = "KNOWLEDGE_BRAIN",
    ) -> None:
        super().__init__(connection_factory, database=database, schema=schema)

    def replace(self, snapshot: KnowledgeGraphSnapshot) -> None:
        """Upsert canonical nodes and replace one DNA version's relationships."""
        self.replace_many((snapshot,))

    def replace_many(self, snapshots: tuple[KnowledgeGraphSnapshot, ...]) -> None:
        """Atomically replace multiple projections using bounded Snowflake batches."""
        if not snapshots:
            return
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            self._upsert_nodes(cursor, snapshots)
            placeholders = ", ".join("%s" for _snapshot in snapshots)
            cursor.execute(
                f"""DELETE FROM {self._table("KNOWLEDGE_GRAPH_EDGES")}
                WHERE dna_id IN ({placeholders})""",
                tuple(snapshot.dna_id for snapshot in snapshots),
            )
            self._insert_edges(cursor, snapshots)
            self._upsert_runs(cursor, snapshots)
            connection.commit()
        except SnowflakeError as exception:
            if connection is not None:
                connection.rollback()
            raise GraphPersistenceError(
                "Snowflake graph projection transaction failed",
                projection_id=(snapshots[0].projection_id if len(snapshots) == 1 else "bulk"),
                sqlstate=exception.sqlstate,
                errno=exception.errno,
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _upsert_nodes(
        self, cursor: CursorProtocol, snapshots: tuple[KnowledgeGraphSnapshot, ...]
    ) -> None:
        nodes = {node.node_id: node for snapshot in snapshots for node in snapshot.nodes}.values()
        rows = tuple(
            (
                node.node_id,
                node.node_type.value,
                node.normalized_key,
                node.display_name,
                node.updated_at,
                node.updated_at,
            )
            for node in nodes
        )
        row_template = "(%s, %s, %s, %s, %s, %s)"
        for row_batch in batched(rows, _NODE_UPSERT_BATCH_SIZE, strict=False):
            values_clause = ", ".join(row_template for _row in row_batch)
            parameters = tuple(value for row in row_batch for value in row)
            cursor.execute(
                f"""MERGE INTO {self._table("KNOWLEDGE_GRAPH_NODES")} target
                USING (SELECT column1 node_id, column2 node_type, column3 normalized_key,
                              column4 display_name, column5 created_at, column6 updated_at
                       FROM VALUES {values_clause}) source
                ON target.node_id = source.node_id
                WHEN MATCHED THEN UPDATE SET display_name = source.display_name,
                    updated_at = source.updated_at
                WHEN NOT MATCHED THEN INSERT
                    (node_id, node_type, normalized_key, display_name, created_at, updated_at)
                    VALUES (source.node_id, source.node_type, source.normalized_key,
                            source.display_name, source.created_at, source.updated_at)""",
                parameters,
            )

    def _insert_edges(
        self, cursor: CursorProtocol, snapshots: tuple[KnowledgeGraphSnapshot, ...]
    ) -> None:
        rows = tuple(
            (
                edge.edge_id,
                edge.project_id,
                edge.dna_id,
                edge.source_node_id,
                edge.target_node_id,
                edge.relationship_type.value,
                edge.confidence,
                json.dumps([asdict(item) for item in edge.evidence], separators=(",", ":")),
                edge.created_at,
            )
            for snapshot in snapshots
            for edge in snapshot.edges
        )
        row_template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        for row_batch in batched(rows, _EDGE_INSERT_BATCH_SIZE, strict=False):
            values_clause = ", ".join(row_template for _row in row_batch)
            parameters = tuple(value for row in row_batch for value in row)
            cursor.execute(
                f"""INSERT INTO {self._table("KNOWLEDGE_GRAPH_EDGES")}
                (edge_id, project_id, dna_id, source_node_id, target_node_id,
                 relationship_type, claim_confidence, evidence, created_at)
                SELECT column1, column2, column3, column4, column5, column6, column7,
                       PARSE_JSON(column8), column9
                FROM VALUES {values_clause}""",
                parameters,
            )

    def _upsert_runs(
        self, cursor: CursorProtocol, snapshots: tuple[KnowledgeGraphSnapshot, ...]
    ) -> None:
        rows = tuple(
            (
                snapshot.projection_id,
                snapshot.projection_version,
                snapshot.project_id,
                snapshot.dna_id,
                len(snapshot.nodes),
                len(snapshot.edges),
                snapshot.projected_at,
            )
            for snapshot in snapshots
        )
        row_template = "(%s, %s, %s, %s, %s, %s, %s)"
        for row_batch in batched(rows, _RUN_UPSERT_BATCH_SIZE, strict=False):
            values_clause = ", ".join(row_template for _row in row_batch)
            parameters = tuple(value for row in row_batch for value in row)
            cursor.execute(
                f"""MERGE INTO {self._table("GRAPH_PROJECTION_RUNS")} target
                USING (SELECT column1 projection_id, column2 projection_version,
                              column3 project_id, column4 dna_id, column5 node_count,
                              column6 edge_count, column7 projected_at
                       FROM VALUES {values_clause}) source
                ON target.projection_id = source.projection_id
                WHEN MATCHED THEN UPDATE SET node_count = source.node_count,
                    edge_count = source.edge_count, projected_at = source.projected_at,
                    status = 'completed'
                WHEN NOT MATCHED THEN INSERT
                    (projection_id, projection_version, project_id, dna_id, status,
                     node_count, edge_count, projected_at)
                    VALUES (source.projection_id, source.projection_version, source.project_id,
                            source.dna_id, 'completed', source.node_count, source.edge_count,
                            source.projected_at)""",
                parameters,
            )


class SnowflakeProjectDNAReader(_SnowflakeRepository):
    """Load current persisted DNA records for deterministic graph projection."""

    def load_current(self, *, unprojected_only: bool = True) -> tuple[ProjectDNA, ...]:
        join = (
            f"""LEFT JOIN {self._table("GRAPH_PROJECTION_RUNS")} run
                ON run.dna_id = dna.dna_id AND run.projection_version = 1
                AND run.status = 'completed'"""
            if unprojected_only
            else ""
        )
        predicate = "AND run.projection_id IS NULL" if unprojected_only else ""
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(
                f"""SELECT dna.dna_json
                FROM {self._table("PROJECTS")} project
                INNER JOIN {self._table("PROJECT_DNA")} dna
                    ON dna.dna_id = project.current_dna_id
                {join}
                WHERE 1 = 1 {predicate}
                ORDER BY project.project_id"""
            )
            return tuple(project_dna_from_json(row[0]) for row in cursor.fetchall())
        except (SnowflakeError, TypeError, ValueError, KeyError) as exception:
            raise IntelligenceCorpusError("Current Project DNA load failed") from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()


class SnowflakeIntelligenceRepository(_SnowflakeRepository):
    """Load current Project DNA vectors and graph attributes before indexing."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        database: str,
        schema: str = "KNOWLEDGE_BRAIN",
        embedding_dimensions: int = 3072,
    ) -> None:
        super().__init__(connection_factory, database=database, schema=schema)
        if embedding_dimensions <= 0:
            raise ValueError("embedding_dimensions must be greater than zero")
        self._embedding_dimensions = embedding_dimensions

    def load(self, scope: IntelligenceScope) -> tuple[ProjectIntelligenceRecord, ...]:
        """Load only current DNA records for allowlisted projects."""
        placeholders = ", ".join("%s" for _ in scope.project_ids)
        connection: ConnectionProtocol | None = None
        cursor: CursorProtocol | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(
                f"""SELECT p.project_id, p.current_dna_id, p.display_name, e.vector::ARRAY
                FROM {self._table("PROJECTS")} p
                INNER JOIN {self._table("EMBEDDINGS")} e
                    ON e.project_id = p.project_id
                    AND e.target_type = 'project_dna'
                    AND e.target_id = p.current_dna_id
                WHERE p.project_id IN ({placeholders}) AND e.dimensions = %s
                ORDER BY p.project_id""",
                (*scope.project_ids, self._embedding_dimensions),
            )
            project_rows = cursor.fetchall()
            cursor.execute(
                f"""SELECT edge.project_id, edge.relationship_type, node.node_id,
                           node.display_name, edge.evidence
                FROM {self._table("KNOWLEDGE_GRAPH_EDGES")} edge
                INNER JOIN {self._table("KNOWLEDGE_GRAPH_NODES")} node
                    ON node.node_id = edge.target_node_id
                INNER JOIN {self._table("PROJECTS")} project
                    ON project.project_id = edge.project_id
                    AND project.current_dna_id = edge.dna_id
                WHERE edge.project_id IN ({placeholders})
                ORDER BY edge.project_id, edge.relationship_type, node.display_name""",
                scope.project_ids,
            )
            graph_rows = cursor.fetchall()
            return self._map(project_rows, graph_rows)
        except (SnowflakeError, ValueError, TypeError, KeyError) as exception:
            raise IntelligenceCorpusError(
                "Snowflake intelligence corpus load failed",
                project_count=len(scope.project_ids),
            ) from exception
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _map(
        self,
        project_rows: list[tuple[Any, ...]],
        graph_rows: list[tuple[Any, ...]],
    ) -> tuple[ProjectIntelligenceRecord, ...]:
        attributes: dict[str, dict[str, list[Any]]] = {}
        for row in graph_rows:
            if len(row) != 5:
                raise ValueError("Snowflake returned an unexpected graph row shape")
            project_id = str(row[0])
            relationship = RelationshipType(str(row[1]))
            bucket = attributes.setdefault(project_id, {})
            if relationship is RelationshipType.INVOLVED_EXPERT:
                bucket.setdefault("experts", []).append(
                    ExpertAssociation(
                        expert_id=str(row[2]),
                        name=str(row[3]),
                        evidence=self._evidence(row[4]),
                    )
                )
            elif field := self._attribute_field(relationship):
                bucket.setdefault(field, []).append(str(row[3]))

        records: list[ProjectIntelligenceRecord] = []
        for row in project_rows:
            if len(row) != 4:
                raise ValueError("Snowflake returned an unexpected project intelligence row shape")
            project_id = str(row[0])
            raw_vector = json.loads(row[3]) if isinstance(row[3], str) else row[3]
            if not isinstance(raw_vector, (list, tuple)):
                raise TypeError("Snowflake Project DNA vector must be an array")
            vector = tuple(float(value) for value in raw_vector)
            if len(vector) != self._embedding_dimensions:
                raise ValueError("Project DNA vector dimensions do not match configuration")
            values = attributes.get(project_id, {})
            records.append(
                ProjectIntelligenceRecord(
                    project_id=project_id,
                    dna_id=str(row[1]),
                    display_name=str(row[2]),
                    embedding=vector,
                    industries=tuple(values.get("industries", [])),
                    use_cases=tuple(values.get("use_cases", [])),
                    capabilities=tuple(values.get("capabilities", [])),
                    technologies=tuple(values.get("technologies", [])),
                    cloud_platforms=tuple(values.get("cloud_platforms", [])),
                    experts=tuple(values.get("experts", [])),
                )
            )
        return tuple(records)

    @staticmethod
    def _evidence(raw: object) -> tuple[GraphEvidence, ...]:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(parsed, list):
            raise TypeError("Graph evidence must be an array")
        evidence: list[GraphEvidence] = []
        for item in parsed:
            if not isinstance(item, dict):
                raise TypeError("Every graph evidence item must be an object")
            evidence.append(
                GraphEvidence(
                    document_id=str(item["document_id"]),
                    section_sequence=int(item["section_sequence"]),
                    quote=str(item["quote"]),
                )
            )
        return tuple(evidence)

    @staticmethod
    def _attribute_field(relationship: RelationshipType) -> str | None:
        return {
            RelationshipType.IN_INDUSTRY: "industries",
            RelationshipType.HAS_USE_CASE: "use_cases",
            RelationshipType.HAS_CAPABILITY: "capabilities",
            RelationshipType.USES_TECHNOLOGY: "technologies",
            RelationshipType.USES_CLOUD_PLATFORM: "cloud_platforms",
        }.get(relationship)
