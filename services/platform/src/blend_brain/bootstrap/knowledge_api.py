"""Composition root for authenticated knowledge API services."""

from typing import TYPE_CHECKING, cast

from blend_brain.bootstrap.business_artifacts import create_business_artifact_services
from blend_brain.bootstrap.configuration import Settings
from blend_brain.bootstrap.intelligence import create_organizational_intelligence_services
from blend_brain.bootstrap.retrieval import (
    create_hybrid_retrieval_service,
    create_question_answering_service,
)
from blend_brain.entrypoints.api.auth import StaticBearerAuthenticator
from blend_brain.entrypoints.api.services import KnowledgeApiServices
from blend_brain.knowledge_catalog.application import KnowledgeCatalogService
from blend_brain.knowledge_catalog.infrastructure import SnowflakeKnowledgeCatalogRepository
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig

if TYPE_CHECKING:
    from blend_brain.knowledge_catalog.infrastructure.snowflake import ConnectionFactory


def create_knowledge_api_services(settings: Settings) -> KnowledgeApiServices:
    """Build the authenticated read service graph from validated configuration."""
    if not settings.api_auth_enabled or settings.api_static_bearer_token is None:
        raise ValueError("Authenticated knowledge APIs require local bearer authentication")
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
        query_tag="blend-knowledge-brain:knowledge-api",
    )
    connection_factory = cast("ConnectionFactory", SnowflakeConnectionFactory(config))
    intelligence = create_organizational_intelligence_services(settings)
    retriever = create_hybrid_retrieval_service(settings)
    return KnowledgeApiServices(
        authenticator=StaticBearerAuthenticator(
            enabled=True,
            token=settings.api_static_bearer_token.get_secret_value(),
            subject=settings.api_static_subject,
            project_ids=tuple(settings.api_static_project_ids),
        ),
        catalog=KnowledgeCatalogService(
            SnowflakeKnowledgeCatalogRepository(
                connection_factory, database=config.database, schema=config.schema
            )
        ),
        question_answering=create_question_answering_service(settings, retriever),
        retrieval_indexes=retriever,
        project_similarity=intelligence.project_similarity,
        expert_finder=intelligence.expert_finder,
        intelligence_indexes=intelligence.index_registry,
        knowledge_graph=intelligence.knowledge_graph,
        artifacts=create_business_artifact_services(settings),
    )
