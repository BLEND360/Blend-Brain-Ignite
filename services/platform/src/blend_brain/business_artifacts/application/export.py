"""Private PDF export orchestration with compensating cleanup."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from blend_brain.business_artifacts.domain import (
    ArtifactActor,
    ArtifactAuthorizationError,
    ArtifactExport,
    ArtifactExportError,
    ArtifactKind,
    ArtifactNotFoundError,
    ArtifactPermission,
    ArtifactRequestError,
    ArtifactScope,
    BusinessArtifactError,
)

if TYPE_CHECKING:
    from blend_brain.business_artifacts.application.ports import (
        ArtifactObjectStore,
        BusinessArtifactRepository,
        Clock,
        IdentifierGenerator,
        PdfRenderer,
    )

PDF_CONTENT_TYPE = "application/pdf"


class PdfExportService:
    """Render, privately store, and audit one authorized draft PDF."""

    def __init__(
        self,
        repository: BusinessArtifactRepository,
        renderer: PdfRenderer,
        object_store: ArtifactObjectStore,
        clock: Clock,
        identifiers: IdentifierGenerator,
        *,
        object_prefix: str = "business-artifacts",
        max_pdf_bytes: int = 15_000_000,
    ) -> None:
        if max_pdf_bytes <= 0:
            raise ValueError("max_pdf_bytes must be greater than zero")
        normalized_prefix = object_prefix.strip().strip("/")
        if not normalized_prefix:
            raise ValueError("object_prefix cannot be empty")
        self._repository = repository
        self._renderer = renderer
        self._object_store = object_store
        self._clock = clock
        self._identifiers = identifiers
        self._object_prefix = normalized_prefix
        self._max_pdf_bytes = max_pdf_bytes

    def export(
        self,
        artifact_id: str,
        kind: ArtifactKind,
        *,
        actor: ArtifactActor,
        scope: ArtifactScope,
    ) -> ArtifactExport:
        """Export a scoped artifact and persist its private-object metadata."""
        normalized_id = artifact_id.strip()
        if not normalized_id:
            raise ArtifactRequestError("artifact_id cannot be empty")
        if ArtifactPermission.EXPORT not in actor.permissions:
            raise ArtifactAuthorizationError("Actor is not authorized to export artifacts")
        artifact = self._repository.get_artifact(normalized_id, kind, scope)
        if artifact is None:
            raise ArtifactNotFoundError("Artifact was not found in the authorized project scope")
        try:
            content = self._renderer.render(artifact)
        except BusinessArtifactError:
            raise
        except Exception as exception:
            raise ArtifactExportError("PDF renderer failed") from exception
        if not content.startswith(b"%PDF-") or len(content) > self._max_pdf_bytes:
            raise ArtifactExportError("PDF output is invalid or exceeds its configured limit")
        export_id = self._identifiers.new()
        key = f"{self._object_prefix}/{kind.value}/{artifact.artifact_id}/{export_id}.pdf"
        stored = self._object_store.put(key, content, PDF_CONTENT_TYPE)
        export = ArtifactExport(
            export_id=export_id,
            artifact_id=artifact.artifact_id,
            artifact_kind=kind,
            storage_location=stored.storage_location,
            object_key=stored.key,
            content_type=PDF_CONTENT_TYPE,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            created_by=actor.actor_id,
            created_at=self._clock.now(),
        )
        try:
            self._repository.record_export(export)
        except BusinessArtifactError:
            try:
                self._object_store.delete(stored.key)
            except Exception as cleanup_error:
                raise ArtifactExportError(
                    "Export metadata failed and object cleanup was unsuccessful",
                    object_key=stored.key,
                ) from cleanup_error
            raise
        return export
