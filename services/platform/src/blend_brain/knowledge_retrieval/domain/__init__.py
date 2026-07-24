"""Public domain API for knowledge retrieval."""

from .errors import (
    AnswerGenerationError,
    CorpusLoadError,
    InvalidRetrievalRequestError,
    QueryEmbeddingError,
    RetrievalError,
    UngroundedAnswerError,
)
from .models import (
    AnswerCitation,
    AnswerConfidence,
    ConfidenceBand,
    ConfidenceBreakdown,
    GeneratedAnswerDraft,
    GeneratedCitationDraft,
    GeneratedClaimDraft,
    GroundedAnswer,
    GroundedAnswerClaim,
    IndexedSection,
    RetrievalHit,
    RetrievalScope,
)

__all__ = [
    "AnswerCitation",
    "AnswerConfidence",
    "AnswerGenerationError",
    "ConfidenceBand",
    "ConfidenceBreakdown",
    "CorpusLoadError",
    "GeneratedAnswerDraft",
    "GeneratedCitationDraft",
    "GeneratedClaimDraft",
    "GroundedAnswer",
    "GroundedAnswerClaim",
    "IndexedSection",
    "InvalidRetrievalRequestError",
    "QueryEmbeddingError",
    "RetrievalError",
    "RetrievalHit",
    "RetrievalScope",
    "UngroundedAnswerError",
]
