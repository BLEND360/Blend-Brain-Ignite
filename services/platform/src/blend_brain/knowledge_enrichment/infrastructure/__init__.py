"""External service adapters for Phase 3."""

from blend_brain.knowledge_enrichment.infrastructure.openai_embeddings import (
    OpenAIEmbeddingGateway,
)
from blend_brain.knowledge_enrichment.infrastructure.openai_project_dna import (
    OpenAIProjectDNAGenerator,
)
from blend_brain.knowledge_enrichment.infrastructure.snowflake import (
    SnowflakeConnectionFactory,
    SnowflakeKnowledgeRepository,
)

__all__ = [
    "OpenAIEmbeddingGateway",
    "OpenAIProjectDNAGenerator",
    "SnowflakeConnectionFactory",
    "SnowflakeKnowledgeRepository",
]
