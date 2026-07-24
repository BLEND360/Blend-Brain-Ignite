"""Exact token-counting adapter isolated from model workflows."""

from __future__ import annotations

from typing import Protocol

import tiktoken


class TokenCounter(Protocol):
    """Count model tokens for one text value."""

    def count(self, text: str) -> int:
        """Return the exact encoded-token count."""
        ...


class TiktokenTokenCounter:
    """Count tokens with the model encoding and a controlled fallback."""

    def __init__(self, model: str, *, fallback_encoding: str) -> None:
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoding = tiktoken.get_encoding(fallback_encoding)

    def count(self, text: str) -> int:
        """Return the exact encoded-token count."""
        return len(self._encoding.encode(text))
