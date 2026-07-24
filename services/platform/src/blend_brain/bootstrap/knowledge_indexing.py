"""Backfill deterministic graph projections and verify scoped FAISS indexes."""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, cast

from blend_brain.bootstrap.configuration import Settings
from blend_brain.bootstrap.knowledge_api import create_knowledge_api_services
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig
from blend_brain.knowledge_retrieval.domain import RetrievalScope
from blend_brain.organizational_intelligence.application import KnowledgeGraphProjector
from blend_brain.organizational_intelligence.domain import IntelligenceScope
from blend_brain.organizational_intelligence.infrastructure import (
    SnowflakeKnowledgeGraphRepository,
    SnowflakeProjectDNAReader,
)

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.infrastructure.snowflake import ConnectionFactory


def main(arguments: list[str] | None = None) -> int:
    """Project missing graphs and build both exact authorized index snapshots."""
    options = _parser().parse_args(arguments)
    settings = Settings()
    services = create_knowledge_api_services(settings)
    reader, graph_repository = _repositories(settings)
    dna_records = reader.load_current(unprojected_only=not options.rebuild_graphs)
    projector = KnowledgeGraphProjector()
    snapshots = tuple(projector.project(dna) for dna in dna_records)
    if snapshots:
        sys.stdout.write(f"projecting {len(snapshots)} graph snapshots atomically\n")
        sys.stdout.flush()
        graph_repository.replace_many(snapshots)
    node_count = sum(len(snapshot.nodes) for snapshot in snapshots)
    edge_count = sum(len(snapshot.edges) for snapshot in snapshots)

    project_ids = services.catalog.resolve_scope(tuple(settings.api_static_project_ids))
    if not project_ids:
        raise RuntimeError("No authorized projects are available for indexing")
    section_count = services.retrieval_indexes.refresh(RetrievalScope(project_ids))
    intelligence_count = services.intelligence_indexes.refresh(IntelligenceScope(project_ids))
    sys.stdout.write(
        json.dumps(
            {
                "graphProjects": len(dna_records),
                "graphNodesProcessed": node_count,
                "graphEdgesProcessed": edge_count,
                "retrievalSections": section_count,
                "intelligenceProjects": intelligence_count,
                "authorizedProjects": len(project_ids),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _repositories(
    settings: Settings,
) -> tuple[SnowflakeProjectDNAReader, SnowflakeKnowledgeGraphRepository]:
    config = SnowflakeConnectionConfig(
        account=settings.snowflake_account or "",
        user=settings.snowflake_user or "",
        warehouse=settings.snowflake_warehouse or "",
        database=settings.snowflake_database or "",
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
        password=(
            settings.snowflake_password.get_secret_value() if settings.snowflake_password else None
        ),
        private_key_file=settings.snowflake_private_key_file,
        private_key_file_password=(
            settings.snowflake_private_key_file_password.get_secret_value()
            if settings.snowflake_private_key_file_password
            else None
        ),
        query_tag="blend-knowledge-brain:knowledge-indexing",
    )
    factory = cast("ConnectionFactory", SnowflakeConnectionFactory(config))
    return (
        SnowflakeProjectDNAReader(factory, database=config.database, schema=config.schema),
        SnowflakeKnowledgeGraphRepository(factory, database=config.database, schema=config.schema),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Blend Brain graph and FAISS indexes")
    parser.add_argument(
        "--rebuild-graphs",
        action="store_true",
        help="Reproject every current DNA instead of only missing projections.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
