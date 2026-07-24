"""Dependency-inversion ports owned by the ingestion application layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import (
        DocumentFormat,
        DocumentSource,
        ExtractedDocument,
    )


class DocumentSourceLoader(Protocol):
    """Load a bounded document from an external storage provider."""

    def load(self, source_id: str) -> DocumentSource:
        """Load and fingerprint one source."""
        ...


class DocumentFormatDetector(Protocol):
    """Validate and identify source content."""

    def detect(self, source: DocumentSource) -> DocumentFormat:
        """Return the verified format of a source."""
        ...


class DocumentParser(Protocol):
    """Convert one verified format into the normalized domain model."""

    @property
    def document_format(self) -> DocumentFormat:
        """Return the format supported by this parser."""
        ...

    def parse(self, source: DocumentSource) -> ExtractedDocument:
        """Extract source text and metadata."""
        ...
