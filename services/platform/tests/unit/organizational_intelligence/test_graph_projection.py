"""Knowledge graph projection tests."""

from dataclasses import replace

from blend_brain.organizational_intelligence.application import (
    KnowledgeGraphProjector,
    KnowledgeGraphService,
)
from blend_brain.organizational_intelligence.domain import (
    KnowledgeGraphSnapshot,
    NodeType,
    RelationshipType,
)
from tests.unit.knowledge_enrichment.helpers import claim, dna


def test_projector_creates_deterministic_evidence_backed_graph() -> None:
    source = replace(
        dna(),
        client_name=claim("Example Co"),
        industry=claim("Retail"),
        engagement_type=claim("Data and AI"),
        capabilities=(claim("Forecasting"),),
        experts=(claim("Jane Expert"),),
    )
    projector = KnowledgeGraphProjector()

    first = projector.project(source)
    second = projector.project(source)

    assert first == second
    assert {node.node_type for node in first.nodes} >= {
        NodeType.PROJECT,
        NodeType.CLIENT,
        NodeType.INDUSTRY,
        NodeType.EXPERT,
    }
    assert {edge.relationship_type for edge in first.edges} >= {
        RelationshipType.HAS_CLIENT,
        RelationshipType.INVOLVED_EXPERT,
        RelationshipType.USES_TECHNOLOGY,
    }
    expert_edge = next(
        edge for edge in first.edges if edge.relationship_type is RelationshipType.INVOLVED_EXPERT
    )
    assert expert_edge.evidence[0].document_id == source.document_id
    assert first.projection_version == 1


def test_projector_deduplicates_normalized_entities_and_merges_evidence() -> None:
    source = replace(
        dna(),
        technologies=(claim("Snowflake"), claim("  snowflake  ")),
    )

    snapshot = KnowledgeGraphProjector().project(source)

    technology_nodes = [node for node in snapshot.nodes if node.node_type is NodeType.TECHNOLOGY]
    technology_edges = [
        edge
        for edge in snapshot.edges
        if edge.relationship_type is RelationshipType.USES_TECHNOLOGY
    ]
    assert len(technology_nodes) == 1
    assert len(technology_edges) == 1


def test_graph_service_persists_projected_snapshot() -> None:
    persisted = []

    class Repository:
        def replace(self, snapshot: KnowledgeGraphSnapshot) -> None:
            persisted.append(snapshot)

    service = KnowledgeGraphService(KnowledgeGraphProjector(), Repository())
    snapshot = service.rebuild(dna())

    assert persisted == [snapshot]
