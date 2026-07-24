"""Request correlation context independent of the HTTP framework."""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str] = ContextVar("request_id", default="unavailable")


def get_request_id() -> str:
    """Return the current request correlation identifier."""
    return _request_id.get()


def set_request_id(value: str) -> Token[str]:
    """Bind a request identifier and return its reset token."""
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request identifier context."""
    _request_id.reset(token)
