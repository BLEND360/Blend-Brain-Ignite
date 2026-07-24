"""Deterministic Project DNA to knowledge graph projection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from blend_brain.knowledge_enrichment.domain import ClaimConfidence, GroundedClaim, ProjectDNA
from blend_brain.organizational_intelligence.domain import (
    GraphEdge,
    GraphEvidence,
    GraphNode,
    KnowledgeGraphSnapshot,
    NodeType,
    RelationshipType,
)

if TYPE_CHECKING:
    from datetime import datetime

    from blend_brain.organizational_intelligence.application.ports import KnowledgeGraphRepository

PROJECTION_VERSION = 1
_WHITESPACE = re.compile(r"\s+")
_CONFIDENCE_ORDER = {ClaimConfidence.LOW: 0, ClaimConfidence.MEDIUM: 1, ClaimConfidence.HIGH: 2}


@dataclass(slots=True)
class _EdgeDraft:
    """Mutable local aggregation state hidden behind the immutable domain boundary."""

    node: GraphNode
    relationship: RelationshipType
    confidence: ClaimConfidence
    evidence: list[GraphEvidence]


class KnowledgeGraphProjector:
    """Project only evidence-backed Project DNA claims into canonical graph entities."""

    def project(self, dna: ProjectDNA) -> KnowledgeGraphSnapshot:
        """Create an idempotent graph snapshot without an additional model call."""
        project_name = dna.project_name.value if dna.project_name else dna.project_id
        project_node = self._project_node(dna.project_id, project_name, dna.generated_at)
        nodes: dict[str, GraphNode] = {project_node.node_id: project_node}
        drafts: dict[tuple[RelationshipType, str], _EdgeDraft] = {}

        def add(node_type: NodeType, relationship: RelationshipType, claim: GroundedClaim) -> None:
            normalized = self._normalize(claim.value)
            node = self._entity_node(node_type, normalized, claim.value, dna.generated_at)
            nodes[node.node_id] = node
            key = (relationship, node.node_id)
            evidence = [
                GraphEvidence(dna.document_id, item.section_sequence, item.quote)
                for item in claim.evidence
            ]
            existing = drafts.get(key)
            if existing is None:
                drafts[key] = _EdgeDraft(node, relationship, claim.confidence, evidence)
                return
            if _CONFIDENCE_ORDER[claim.confidence] > _CONFIDENCE_ORDER[existing.confidence]:
                existing.confidence = claim.confidence
            known = {
                (item.document_id, item.section_sequence, item.quote) for item in existing.evidence
            }
            existing.evidence.extend(
                item
                for item in evidence
                if (item.document_id, item.section_sequence, item.quote) not in known
            )

        scalar = (
            (NodeType.CLIENT, RelationshipType.HAS_CLIENT, dna.client_name),
            (NodeType.INDUSTRY, RelationshipType.IN_INDUSTRY, dna.industry),
            (
                NodeType.ENGAGEMENT_TYPE,
                RelationshipType.HAS_ENGAGEMENT_TYPE,
                dna.engagement_type,
            ),
        )
        for node_type, relationship, claim in scalar:
            if claim is not None:
                add(node_type, relationship, claim)

        collections = (
            (NodeType.USE_CASE, RelationshipType.HAS_USE_CASE, dna.use_cases),
            (NodeType.CAPABILITY, RelationshipType.HAS_CAPABILITY, dna.capabilities),
            (NodeType.TECHNOLOGY, RelationshipType.USES_TECHNOLOGY, dna.technologies),
            (NodeType.DATA_SOURCE, RelationshipType.USES_DATA_SOURCE, dna.data_sources),
            (
                NodeType.CLOUD_PLATFORM,
                RelationshipType.USES_CLOUD_PLATFORM,
                dna.cloud_platforms,
            ),
            (NodeType.OUTCOME, RelationshipType.DELIVERED_OUTCOME, dna.outcomes),
            (
                NodeType.DIFFERENTIATOR,
                RelationshipType.HAS_DIFFERENTIATOR,
                dna.differentiators,
            ),
            (NodeType.EXPERT, RelationshipType.INVOLVED_EXPERT, dna.experts),
        )
        for node_type, relationship, claims in collections:
            for claim in claims:
                add(node_type, relationship, claim)

        edges = tuple(
            self._edge(dna, project_node, draft)
            for _, draft in sorted(drafts.items(), key=lambda item: (item[0][0].value, item[0][1]))
        )
        projection_id = str(
            uuid5(NAMESPACE_URL, f"blend-brain:graph:{dna.dna_id}:v{PROJECTION_VERSION}")
        )
        return KnowledgeGraphSnapshot(
            projection_id=projection_id,
            projection_version=PROJECTION_VERSION,
            project_id=dna.project_id,
            dna_id=dna.dna_id,
            nodes=tuple(sorted(nodes.values(), key=lambda node: node.node_id)),
            edges=edges,
            projected_at=dna.generated_at,
        )

    @classmethod
    def _project_node(cls, project_id: str, name: str, at: datetime) -> GraphNode:
        return GraphNode(
            node_id=str(uuid5(NAMESPACE_URL, f"blend-brain:graph:project:{project_id}")),
            node_type=NodeType.PROJECT,
            normalized_key=project_id,
            display_name=name.strip(),
            updated_at=at,
        )

    @staticmethod
    def _entity_node(node_type: NodeType, key: str, name: str, at: datetime) -> GraphNode:
        return GraphNode(
            node_id=str(uuid5(NAMESPACE_URL, f"blend-brain:graph:{node_type.value}:{key}")),
            node_type=node_type,
            normalized_key=key,
            display_name=name.strip(),
            updated_at=at,
        )

    @staticmethod
    def _edge(dna: ProjectDNA, project: GraphNode, draft: _EdgeDraft) -> GraphEdge:
        edge_id = str(
            uuid5(
                NAMESPACE_URL,
                f"blend-brain:graph:{dna.dna_id}:{draft.relationship.value}:{draft.node.node_id}",
            )
        )
        return GraphEdge(
            edge_id=edge_id,
            project_id=dna.project_id,
            dna_id=dna.dna_id,
            source_node_id=project.node_id,
            target_node_id=draft.node.node_id,
            relationship_type=draft.relationship,
            confidence=draft.confidence.value,
            evidence=tuple(draft.evidence),
            created_at=dna.generated_at,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return _WHITESPACE.sub(" ", value).strip().casefold()


class KnowledgeGraphService:
    """Project and atomically persist one Project DNA graph snapshot."""

    def __init__(
        self,
        projector: KnowledgeGraphProjector,
        repository: KnowledgeGraphRepository,
    ) -> None:
        self._projector = projector
        self._repository = repository

    def rebuild(self, dna: ProjectDNA) -> KnowledgeGraphSnapshot:
        """Replace the graph projection for a DNA version and return it."""
        snapshot = self._projector.project(dna)
        self._repository.replace(snapshot)
        return snapshot
