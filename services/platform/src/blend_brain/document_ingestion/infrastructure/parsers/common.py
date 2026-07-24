"""Shared parser normalization and result construction."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from blend_brain.document_ingestion.domain import (
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    DocumentSource,
    EmptyDocumentError,
    ExtractedDocument,
    ExtractionWarning,
)

_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(value: str) -> str:
    """Normalize control characters and line endings without flattening structure."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    normalized = "\n".join(line.rstrip() for line in normalized.splitlines())
    return _EXCESS_BLANK_LINES.sub("\n\n", normalized).strip()


def normalize_datetime(value: datetime | None) -> datetime | None:
    """Return timezone-aware UTC metadata timestamps."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def optional_text(value: str | None) -> str | None:
    """Normalize optional metadata and collapse empty values to None."""
    if value is None:
        return None
    normalized = normalize_text(value)
    return normalized or None


def build_document(
    source: DocumentSource,
    document_format: DocumentFormat,
    sections: list[DocumentSection],
    *,
    metadata: DocumentMetadata | None = None,
    warnings: list[ExtractionWarning] | None = None,
) -> ExtractedDocument:
    """Build a normalized document and reject wholly empty extraction."""
    normalized_sections = tuple(
        DocumentSection(
            sequence=index,
            kind=section.kind,
            text=normalize_text(section.text),
            locator=section.locator,
        )
        for index, section in enumerate(sections, start=1)
    )
    if not any(section.text for section in normalized_sections):
        raise EmptyDocumentError(
            "Document contains no extractable text",
            filename=source.filename,
            document_format=document_format.value,
        )
    return ExtractedDocument(
        source_id=source.source_id,
        filename=source.filename,
        document_format=document_format,
        size_bytes=source.size_bytes,
        sha256=source.sha256,
        sections=normalized_sections,
        metadata=metadata or DocumentMetadata(),
        warnings=tuple(warnings or ()),
    )
