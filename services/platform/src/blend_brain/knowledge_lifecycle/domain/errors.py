"""Stable errors for the governed knowledge lifecycle."""

from __future__ import annotations

from typing import Any


class KnowledgeLifecycleError(Exception):
    """Base error carrying a stable machine code and safe context."""

    code = "knowledge_lifecycle_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class KnowledgeRequestError(KnowledgeLifecycleError):
    """A capture or workflow request is invalid."""

    code = "invalid_knowledge_request"


class KnowledgeAuthorizationError(KnowledgeLifecycleError):
    """The actor cannot perform the requested project operation."""

    code = "knowledge_operation_forbidden"


class KnowledgeNotFoundError(KnowledgeLifecycleError):
    """A scoped gap or submission does not exist."""

    code = "knowledge_record_not_found"


class KnowledgeWorkflowConflictError(KnowledgeLifecycleError):
    """The record changed or its current state rejects the transition."""

    code = "knowledge_workflow_conflict"


class KnowledgePersistenceError(KnowledgeLifecycleError):
    """The lifecycle transaction could not be committed."""

    code = "knowledge_persistence_failed"
