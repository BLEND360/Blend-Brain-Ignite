"""Offline tests for the exact tokenizer adapter."""

from unittest.mock import Mock, patch

from blend_brain.knowledge_enrichment.infrastructure.tokens import TiktokenTokenCounter


def test_token_counter_uses_model_encoding() -> None:
    encoding = Mock()
    encoding.encode.return_value = [1, 2, 3]
    with patch(
        "blend_brain.knowledge_enrichment.infrastructure.tokens.tiktoken.encoding_for_model",
        return_value=encoding,
    ):
        counter = TiktokenTokenCounter("model", fallback_encoding="fallback")

    assert counter.count("text") == 3


def test_token_counter_uses_fallback_for_unknown_model() -> None:
    encoding = Mock()
    encoding.encode.return_value = [1]
    with (
        patch(
            "blend_brain.knowledge_enrichment.infrastructure.tokens.tiktoken.encoding_for_model",
            side_effect=KeyError,
        ),
        patch(
            "blend_brain.knowledge_enrichment.infrastructure.tokens.tiktoken.get_encoding",
            return_value=encoding,
        ) as fallback,
    ):
        counter = TiktokenTokenCounter("unknown", fallback_encoding="fallback")

    assert counter.count("text") == 1
    fallback.assert_called_once_with("fallback")
