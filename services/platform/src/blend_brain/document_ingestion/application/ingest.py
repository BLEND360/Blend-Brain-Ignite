"""Document ingestion use case orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blend_brain.document_ingestion.domain import (
    ExtractedDocument,
    UnsupportedDocumentError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from blend_brain.document_ingestion.application.ports import (
        DocumentFormatDetector,
        DocumentParser,
        DocumentSourceLoader,
    )
    from blend_brain.document_ingestion.domain import DocumentFormat


class DocumentIngestionService:
    """Coordinate loading, validation, detection, and extraction."""

    def __init__(
        self,
        loader: DocumentSourceLoader,
        detector: DocumentFormatDetector,
        parsers: Iterable[DocumentParser],
    ) -> None:
        self._loader = loader
        self._detector = detector
        self._parsers = self._build_parser_registry(parsers)

    def ingest(self, source_id: str) -> ExtractedDocument:
        """Ingest one source or raise a stable domain failure."""
        source = self._loader.load(source_id)
        document_format = self._detector.detect(source)
        parser = self._parsers.get(document_format)
        if parser is None:
            raise UnsupportedDocumentError(
                "No parser is registered for the detected document format",
                document_format=document_format.value,
            )
        return parser.parse(source)

    @staticmethod
    def _build_parser_registry(
        parsers: Iterable[DocumentParser],
    ) -> dict[DocumentFormat, DocumentParser]:
        registry: dict[DocumentFormat, DocumentParser] = {}
        for parser in parsers:
            if parser.document_format in registry:
                raise ValueError(f"Duplicate parser for {parser.document_format.value}")
            registry[parser.document_format] = parser
        return registry
