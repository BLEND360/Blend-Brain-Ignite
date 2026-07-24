"""Stable errors for proposal, one-pager, and export workflows."""

from __future__ import annotations

from typing import Any


class BusinessArtifactError(Exception):
    """Base error with a stable code and safe diagnostic context."""

    code = "business_artifact_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class ArtifactRequestError(BusinessArtifactError):
    """Artifact input is invalid or exceeds a configured bound."""

    code = "invalid_artifact_request"


class ArtifactAuthorizationError(BusinessArtifactError):
    """The actor cannot perform the operation for the project scope."""

    code = "artifact_operation_forbidden"


class ArtifactSourceError(BusinessArtifactError):
    """Authorized grounded source material is missing or invalid."""

    code = "artifact_source_failed"


class ArtifactGenerationError(BusinessArtifactError):
    """The model could not produce a valid grounded artifact."""

    code = "artifact_generation_failed"


class UngroundedArtifactError(BusinessArtifactError):
    """Generated content cites text absent from the supplied source."""

    code = "ungrounded_business_artifact"


class ArtifactPersistenceError(BusinessArtifactError):
    """Artifact or export metadata could not be committed."""

    code = "artifact_persistence_failed"


class ArtifactNotFoundError(BusinessArtifactError):
    """An artifact is absent from the authorized scope."""

    code = "business_artifact_not_found"


class ArtifactExportError(BusinessArtifactError):
    """A PDF could not be rendered or durably stored."""

    code = "artifact_export_failed"
