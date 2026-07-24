"""OpenAI batched embedding adapter with strict response validation."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from openai import APIError, OpenAI

from blend_brain.knowledge_enrichment.domain import (
    EmbeddingGenerationError,
    EmbeddingRecord,
    EmbeddingTarget,
    EnrichmentInputTooLargeError,
)
from blend_brain.knowledge_enrichment.infrastructure.tokens import (
    TiktokenTokenCounter,
    TokenCounter,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class OpenAIEmbeddingGateway:
    """Generate ordered `text-embedding-3-large` vectors in bounded batches."""

    def __init__(
        self,
        client: OpenAI,
        *,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072,
        batch_size: int = 128,
        max_input_tokens: int = 8_192,
        max_batch_tokens: int = 300_000,
        clock: Callable[[], datetime] | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        if min(dimensions, batch_size, max_input_tokens, max_batch_tokens) <= 0:
            raise ValueError("Embedding limits must be greater than zero")
        if batch_size > 2_048:
            raise ValueError("batch_size cannot exceed 2048 inputs")
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._max_input_tokens = max_input_tokens
        self._max_batch_tokens = max_batch_tokens
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_counter = token_counter or TiktokenTokenCounter(
            model, fallback_encoding="cl100k_base"
        )

    def embed(self, targets: tuple[EmbeddingTarget, ...]) -> tuple[EmbeddingRecord, ...]:
        """Generate one validated vector per target while preserving input order."""
        if not targets:
            return ()
        records: list[EmbeddingRecord] = []
        current_targets: list[EmbeddingTarget] = []
        current_tokens = 0
        for target in targets:
            token_count = self._token_counter.count(target.text)
            if token_count > self._max_input_tokens:
                raise EnrichmentInputTooLargeError(
                    "Embedding target exceeds the model token limit",
                    target_id=target.target_id,
                    token_count=token_count,
                    token_limit=self._max_input_tokens,
                )
            if current_targets and (
                len(current_targets) >= self._batch_size
                or current_tokens + token_count > self._max_batch_tokens
            ):
                records.extend(self._embed_batch(current_targets))
                current_targets = []
                current_tokens = 0
            current_targets.append(target)
            current_tokens += token_count
        if current_targets:
            records.extend(self._embed_batch(current_targets))
        return tuple(records)

    def _embed_batch(self, targets: list[EmbeddingTarget]) -> list[EmbeddingRecord]:
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=[target.text for target in targets],
                dimensions=self._dimensions,
                encoding_format="float",
            )
        except APIError as exception:
            raise EmbeddingGenerationError(
                "OpenAI embedding generation failed",
                model=self._model,
                batch_size=len(targets),
            ) from exception
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(targets):
            raise EmbeddingGenerationError(
                "OpenAI returned an unexpected embedding count",
                expected=len(targets),
                actual=len(ordered),
            )
        created_at = self._clock()
        records: list[EmbeddingRecord] = []
        for target, item in zip(targets, ordered, strict=True):
            vector = tuple(float(value) for value in item.embedding)
            if len(vector) != self._dimensions or not all(map(math.isfinite, vector)):
                raise EmbeddingGenerationError(
                    "OpenAI returned an invalid embedding vector",
                    target_id=target.target_id,
                    expected_dimensions=self._dimensions,
                    actual_dimensions=len(vector),
                )
            records.append(
                EmbeddingRecord(
                    embedding_id=target.embedding_id,
                    project_id=target.project_id,
                    document_id=target.document_id,
                    target_type=target.target_type,
                    target_id=target.target_id,
                    section_sequence=target.section_sequence,
                    content_sha256=target.content_sha256,
                    model=self._model,
                    dimensions=self._dimensions,
                    vector=vector,
                    created_at=created_at,
                )
            )
        return records
