"""Stable errors raised by Phase 4 retrieval workflows."""

from __future__ import annotations

from typing import Any


class RetrievalError(Exception):
    """Base error carrying a stable code and safe diagnostic context."""

    code = "retrieval_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class InvalidRetrievalRequestError(RetrievalError):
    """A question or mandatory authorization scope is invalid."""

    code = "invalid_retrieval_request"


class CorpusLoadError(RetrievalError):
    """The scoped retrieval corpus could not be read."""

    code = "retrieval_corpus_load_failed"


class QueryEmbeddingError(RetrievalError):
    """The query embedding could not be generated or validated."""

    code = "query_embedding_failed"


class AnswerGenerationError(RetrievalError):
    """The answer model failed to return a valid structured response."""

    code = "answer_generation_failed"


class UngroundedAnswerError(AnswerGenerationError):
    """A generated answer cites evidence absent from the retrieval context."""

    code = "answer_ungrounded"
