"""Infrastructure adapters for Phase 6."""

from .faiss_intelligence import FaissIntelligenceIndexFactory
from .openai_embeddings import OpenAIIntelligenceEmbeddingGateway
from .snowflake import (
    SnowflakeIntelligenceRepository,
    SnowflakeKnowledgeGraphRepository,
    SnowflakeProjectDNAReader,
)

__all__ = [
    "FaissIntelligenceIndexFactory",
    "OpenAIIntelligenceEmbeddingGateway",
    "SnowflakeIntelligenceRepository",
    "SnowflakeKnowledgeGraphRepository",
    "SnowflakeProjectDNAReader",
]
