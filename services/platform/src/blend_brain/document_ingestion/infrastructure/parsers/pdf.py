"""PDF text and metadata parser adapter."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from blend_brain.document_ingestion.domain import (
    CorruptDocumentError,
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    DocumentSource,
    DocumentTooLargeError,
    EncryptedDocumentError,
    ExtractedDocument,
    ExtractionWarning,
    SectionKind,
    SectionLocator,
)
from blend_brain.document_ingestion.infrastructure.filesystem import IngestionLimits
from blend_brain.document_ingestion.infrastructure.parsers.common import (
    build_document,
    optional_text,
)


class PdfParser:
    """Extract page-addressable text from digital PDFs."""

    def __init__(self, limits: IngestionLimits | None = None) -> None:
        self._limits = limits or IngestionLimits()

    @property
    def document_format(self) -> DocumentFormat:
        """Return the supported format."""
        return DocumentFormat.PDF

    def parse(self, source: DocumentSource) -> ExtractedDocument:
        """Extract text page by page; scanned pages are flagged for future OCR."""
        try:
            reader = PdfReader(BytesIO(source.content), strict=True)
        except (PdfReadError, ValueError, TypeError) as exception:
            raise CorruptDocumentError(
                "PDF document could not be parsed",
                filename=source.filename,
            ) from exception

        if reader.is_encrypted:
            raise EncryptedDocumentError(
                "Password-protected PDF documents are not supported",
                filename=source.filename,
            )
        if len(reader.pages) > self._limits.max_pdf_pages:
            raise DocumentTooLargeError(
                "PDF exceeds the configured page limit",
                filename=source.filename,
                page_count=len(reader.pages),
                page_limit=self._limits.max_pdf_pages,
            )

        try:
            sections: list[DocumentSection] = []
            warnings: list[ExtractionWarning] = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                locator = SectionLocator(page_number=page_number)
                sections.append(
                    DocumentSection(
                        sequence=page_number,
                        kind=SectionKind.PAGE,
                        text=text,
                        locator=locator,
                    )
                )
                if not text.strip():
                    warnings.append(
                        ExtractionWarning(
                            code="page_has_no_extractable_text",
                            message="The page may require OCR",
                            locator=locator,
                        )
                    )
            metadata = self._metadata(reader.metadata)
            return build_document(
                source,
                self.document_format,
                sections,
                metadata=metadata,
                warnings=warnings,
            )
        except (PdfReadError, ValueError, TypeError) as exception:
            raise CorruptDocumentError(
                "PDF document could not be parsed",
                filename=source.filename,
            ) from exception

    @staticmethod
    def _metadata(raw: Any) -> DocumentMetadata:
        if raw is None:
            return DocumentMetadata()
        return DocumentMetadata(
            title=optional_text(getattr(raw, "title", None)),
            author=optional_text(getattr(raw, "author", None)),
            subject=optional_text(getattr(raw, "subject", None)),
        )
