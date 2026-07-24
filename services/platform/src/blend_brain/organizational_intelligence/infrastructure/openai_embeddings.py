"""OpenAI query embedding adapter for Expert Finder."""

from __future__ import annotations

import math
from typing import Protocol

import tiktoken
from openai import APIError, OpenAI

from blend_brain.organizational_intelligence.domain import IntelligenceEmbeddingError


class TokenCounter(Protocol):
    """Count model input tokens."""

    def count(self, text: str) -> int:
        """Return the token count."""
        ...


class _TiktokenCounter:
    def __init__(self, model: str) -> None:
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text, disallowed_special=()))


class OpenAIIntelligenceEmbeddingGateway:
    """Embed an expertise query in the same space as Project DNA vectors."""

    def __init__(
        self,
        client: OpenAI,
        *,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072,
        max_input_tokens: int = 8_192,
        token_counter: TokenCounter | None = None,
    ) -> None:
        if min(dimensions, max_input_tokens) <= 0:
            raise ValueError("Embedding limits must be greater than zero")
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._max_input_tokens = max_input_tokens
        self._token_counter = token_counter or _TiktokenCounter(model)

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Return one validated non-zero expertise-query vector."""
        token_count = self._token_counter.count(query)
        if token_count > self._max_input_tokens:
            raise IntelligenceEmbeddingError(
                "Expert Finder query exceeds the embedding token limit",
                token_count=token_count,
                token_limit=self._max_input_tokens,
            )
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=query,
                dimensions=self._dimensions,
                encoding_format="float",
            )
        except APIError as exception:
            raise IntelligenceEmbeddingError(
                "OpenAI Expert Finder embedding failed", model=self._model
            ) from exception
        if len(response.data) != 1:
            raise IntelligenceEmbeddingError(
                "OpenAI returned an unexpected Expert Finder embedding count",
                actual=len(response.data),
            )
        vector = tuple(float(value) for value in response.data[0].embedding)
        if (
            len(vector) != self._dimensions
            or not all(math.isfinite(value) for value in vector)
            or not any(value != 0.0 for value in vector)
        ):
            raise IntelligenceEmbeddingError(
                "OpenAI returned an invalid Expert Finder embedding",
                expected_dimensions=self._dimensions,
                actual_dimensions=len(vector),
            )
        return vector
