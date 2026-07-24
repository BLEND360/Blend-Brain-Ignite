"""Phase 3 dependency composition without activating an API workflow."""

from typing import cast

from openai import OpenAI

from blend_brain.bootstrap.configuration import Settings
from blend_brain.knowledge_enrichment.application import KnowledgeEnrichmentService
from blend_brain.knowledge_enrichment.infrastructure import (
    OpenAIEmbeddingGateway,
    OpenAIProjectDNAGenerator,
    SnowflakeConnectionFactory,
    SnowflakeKnowledgeRepository,
)
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig


def create_knowledge_enrichment_service(settings: Settings) -> KnowledgeEnrichmentService:
    """Build Phase 3 services only when all external configuration is available."""
    if settings.openai_api_key is None:
        raise ValueError("BLEND_BRAIN_OPENAI_API_KEY is required for Phase 3")
    if not settings.snowflake_enabled:
        raise ValueError("BLEND_BRAIN_SNOWFLAKE_ENABLED must be true for Phase 3")
    if not all(
        (
            settings.snowflake_account,
            settings.snowflake_user,
            settings.snowflake_warehouse,
            settings.snowflake_database,
        )
    ):
        raise ValueError("Snowflake settings are incomplete")
    account = cast("str", settings.snowflake_account)
    user = cast("str", settings.snowflake_user)
    warehouse = cast("str", settings.snowflake_warehouse)
    database = cast("str", settings.snowflake_database)

    openai_client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    snowflake_config = SnowflakeConnectionConfig(
        account=account,
        user=user,
        warehouse=warehouse,
        database=database,
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
    )
    connection_factory = SnowflakeConnectionFactory(snowflake_config)
    repository = SnowflakeKnowledgeRepository(
        connection_factory,
        database=snowflake_config.database,
        schema=snowflake_config.schema,
    )
    return KnowledgeEnrichmentService(
        dna_generator=OpenAIProjectDNAGenerator(
            openai_client,
            model=settings.openai_project_dna_model,
        ),
        embedding_gateway=OpenAIEmbeddingGateway(
            openai_client,
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
        ),
        repository=repository,
    )
