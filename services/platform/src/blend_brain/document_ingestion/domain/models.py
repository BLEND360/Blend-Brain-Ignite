"""Immutable domain values produced by document ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class DocumentFormat(StrEnum):
    """Document formats supported by Phase 2."""

    PPTX = "pptx"
    DOCX = "docx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"


class SectionKind(StrEnum):
    """Semantic unit represented by an extracted section."""

    SLIDE = "slide"
    PAGE = "page"
    HEADING = "heading"
    BODY = "body"


@dataclass(frozen=True, slots=True)
class SectionLocator:
    """Source-native coordinates used by future citation workflows."""

    page_number: int | None = None
    slide_number: int | None = None
    heading: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """One ordered, independently citable block of extracted text."""

    sequence: int
    kind: SectionKind
    text: str
    locator: SectionLocator = field(default_factory=SectionLocator)


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Format-independent metadata with lossless extension fields."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionWarning:
    """A non-fatal extraction limitation visible to downstream workflows."""

    code: str
    message: str
    locator: SectionLocator | None = None


@dataclass(frozen=True, slots=True)
class DocumentSource:
    """Validated source bytes independent of their storage provider."""

    source_id: str
    filename: str
    content: bytes = field(repr=False)
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    """Normalized output shared by all parser adapters."""

    source_id: str
    filename: str
    document_format: DocumentFormat
    size_bytes: int
    sha256: str
    sections: tuple[DocumentSection, ...]
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    warnings: tuple[ExtractionWarning, ...] = ()

    @property
    def text(self) -> str:
        """Return all non-empty sections in source order."""
        return "\n\n".join(section.text for section in self.sections if section.text)
