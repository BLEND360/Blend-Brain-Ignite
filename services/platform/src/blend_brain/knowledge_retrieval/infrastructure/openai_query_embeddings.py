"""OpenAI adapter for validated query embeddings."""

from __future__ import annotations

import math

from openai import APIError, OpenAI

from blend_brain.knowledge_enrichment.infrastructure.tokens import (
    TiktokenTokenCounter,
    TokenCounter,
)
from blend_brain.knowledge_retrieval.domain import QueryEmbeddingError


class OpenAIQueryEmbeddingGateway:
    """Embed one search query with the same model and dimensions as the corpus."""

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
        self._token_counter = token_counter or TiktokenTokenCounter(
            model, fallback_encoding="cl100k_base"
        )

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Return one finite query vector or a stable integration error."""
        token_count = self._token_counter.count(query)
        if token_count > self._max_input_tokens:
            raise QueryEmbeddingError(
                "Query exceeds the embedding token limit",
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
            raise QueryEmbeddingError(
                "OpenAI query embedding generation failed", model=self._model
            ) from exception
        if len(response.data) != 1:
            raise QueryEmbeddingError(
                "OpenAI returned an unexpected query embedding count",
                actual=len(response.data),
            )
        vector = tuple(float(value) for value in response.data[0].embedding)
        if (
            len(vector) != self._dimensions
            or not all(math.isfinite(value) for value in vector)
            or not any(value != 0.0 for value in vector)
        ):
            raise QueryEmbeddingError(
                "OpenAI returned an invalid query embedding",
                expected_dimensions=self._dimensions,
                actual_dimensions=len(vector),
            )
        return vector
