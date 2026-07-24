"""Typed service bundle consumed by HTTP route adapters."""

from dataclasses import dataclass

from blend_brain.bootstrap.business_artifacts import BusinessArtifactServices
from blend_brain.entrypoints.api.auth import StaticBearerAuthenticator
from blend_brain.knowledge_catalog.application import KnowledgeCatalogService
from blend_brain.knowledge_retrieval.application import (
    HybridRetrievalService,
    QuestionAnsweringService,
)
from blend_brain.organizational_intelligence.application import (
    ExpertFinderService,
    IntelligenceIndexRegistry,
    KnowledgeGraphService,
    ProjectSimilarityService,
)


@dataclass(frozen=True, slots=True)
class KnowledgeApiServices:
    """Application services required by authenticated knowledge routes."""

    authenticator: StaticBearerAuthenticator
    catalog: KnowledgeCatalogService
    question_answering: QuestionAnsweringService
    retrieval_indexes: HybridRetrievalService
    project_similarity: ProjectSimilarityService
    expert_finder: ExpertFinderService
    intelligence_indexes: IntelligenceIndexRegistry
    knowledge_graph: KnowledgeGraphService
    artifacts: BusinessArtifactServices | None = None
