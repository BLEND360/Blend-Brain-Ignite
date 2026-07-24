"""Phase 6 organizational intelligence dependency composition."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from openai import OpenAI

from blend_brain.bootstrap.configuration import Settings
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig
from blend_brain.organizational_intelligence.application import (
    ExpertFinderService,
    IntelligenceIndexRegistry,
    KnowledgeGraphProjector,
    KnowledgeGraphService,
    ProjectSimilarityService,
)
from blend_brain.organizational_intelligence.infrastructure import (
    FaissIntelligenceIndexFactory,
    OpenAIIntelligenceEmbeddingGateway,
    SnowflakeIntelligenceRepository,
    SnowflakeKnowledgeGraphRepository,
)

if TYPE_CHECKING:
    from blend_brain.organizational_intelligence.infrastructure.snowflake import ConnectionFactory


@dataclass(frozen=True, slots=True)
class OrganizationalIntelligenceServices:
    """Phase 6 service graph exposed to trusted orchestration layers."""

    knowledge_graph: KnowledgeGraphService
    project_similarity: ProjectSimilarityService
    expert_finder: ExpertFinderService
    index_registry: IntelligenceIndexRegistry


def create_organizational_intelligence_services(
    settings: Settings,
) -> OrganizationalIntelligenceServices:
    """Build Phase 6 services from validated OpenAI and Snowflake settings."""
    if settings.openai_api_key is None:
        raise ValueError("BLEND_BRAIN_OPENAI_API_KEY is required for Phase 6 Expert Finder")
    if not settings.snowflake_enabled:
        raise ValueError("BLEND_BRAIN_SNOWFLAKE_ENABLED must be true for Phase 6")
    if not all(
        (
            settings.snowflake_account,
            settings.snowflake_user,
            settings.snowflake_warehouse,
            settings.snowflake_database,
        )
    ):
        raise ValueError("Snowflake settings are incomplete")
    config = SnowflakeConnectionConfig(
        account=cast("str", settings.snowflake_account),
        user=cast("str", settings.snowflake_user),
        warehouse=cast("str", settings.snowflake_warehouse),
        database=cast("str", settings.snowflake_database),
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
        query_tag="blend-knowledge-brain:phase-6",
    )
    connection_factory = cast("ConnectionFactory", SnowflakeConnectionFactory(config))
    graph_repository = SnowflakeKnowledgeGraphRepository(
        connection_factory, database=config.database, schema=config.schema
    )
    corpus_repository = SnowflakeIntelligenceRepository(
        connection_factory,
        database=config.database,
        schema=config.schema,
        embedding_dimensions=settings.openai_embedding_dimensions,
    )
    index_registry = IntelligenceIndexRegistry(
        corpus_repository,
        FaissIntelligenceIndexFactory(
            minimum_similarity=settings.intelligence_minimum_similarity,
            minimum_expert_score=settings.intelligence_minimum_expert_score,
        ),
        max_cached_scopes=settings.intelligence_max_cached_scopes,
    )
    openai_client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    return OrganizationalIntelligenceServices(
        knowledge_graph=KnowledgeGraphService(KnowledgeGraphProjector(), graph_repository),
        project_similarity=ProjectSimilarityService(
            index_registry, default_limit=settings.intelligence_default_similarity_limit
        ),
        expert_finder=ExpertFinderService(
            index_registry,
            OpenAIIntelligenceEmbeddingGateway(
                openai_client,
                model=settings.openai_embedding_model,
                dimensions=settings.openai_embedding_dimensions,
            ),
            default_limit=settings.intelligence_default_expert_limit,
            max_query_characters=settings.intelligence_max_expert_query_characters,
        ),
        index_registry=index_registry,
    )
