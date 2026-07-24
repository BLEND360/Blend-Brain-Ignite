"""Phase 4 dependency composition without prematurely exposing a public route."""

from typing import TYPE_CHECKING, cast

from openai import OpenAI

from blend_brain.bootstrap.configuration import Settings
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig
from blend_brain.knowledge_retrieval.application import (
    HybridRetrievalService,
    QuestionAnsweringService,
)
from blend_brain.knowledge_retrieval.infrastructure import (
    FaissHybridSearchIndexFactory,
    OpenAIAnswerGenerator,
    OpenAIQueryEmbeddingGateway,
    SnowflakeRetrievalCorpusRepository,
)

if TYPE_CHECKING:
    from blend_brain.knowledge_retrieval.infrastructure.snowflake import ReadConnectionFactory


def create_hybrid_retrieval_service(settings: Settings) -> HybridRetrievalService:
    """Build the scoped hybrid index registry and query embedding adapter."""
    if settings.openai_api_key is None:
        raise ValueError("BLEND_BRAIN_OPENAI_API_KEY is required for Phase 4")
    if not settings.snowflake_enabled:
        raise ValueError("BLEND_BRAIN_SNOWFLAKE_ENABLED must be true for Phase 4")
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
    )
    openai_client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    connection_factory = cast("ReadConnectionFactory", SnowflakeConnectionFactory(config))
    corpus_repository = SnowflakeRetrievalCorpusRepository(
        connection_factory,
        database=config.database,
        schema=config.schema,
        embedding_dimensions=settings.openai_embedding_dimensions,
    )
    return HybridRetrievalService(
        corpus_repository=corpus_repository,
        embedding_gateway=OpenAIQueryEmbeddingGateway(
            openai_client,
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
        ),
        index_factory=FaissHybridSearchIndexFactory(
            rrf_k=settings.retrieval_rrf_k,
            dense_weight=settings.retrieval_dense_weight,
            lexical_weight=settings.retrieval_lexical_weight,
            candidate_multiplier=settings.retrieval_candidate_multiplier,
        ),
        max_cached_scopes=settings.retrieval_max_cached_scopes,
        max_question_characters=settings.retrieval_max_question_characters,
    )


def create_question_answering_service(
    settings: Settings, retriever: HybridRetrievalService | None = None
) -> QuestionAnsweringService:
    """Build grounded answering over one shared hybrid retrieval registry."""
    if settings.openai_api_key is None:
        raise ValueError("BLEND_BRAIN_OPENAI_API_KEY is required for Phase 4")
    resolved_retriever = retriever or create_hybrid_retrieval_service(settings)
    openai_client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    return QuestionAnsweringService(
        retriever=resolved_retriever,
        answer_generator=OpenAIAnswerGenerator(
            openai_client,
            model=settings.openai_question_answer_model,
            max_input_tokens=settings.retrieval_answer_max_input_tokens,
        ),
        default_top_k=settings.retrieval_default_top_k,
    )
