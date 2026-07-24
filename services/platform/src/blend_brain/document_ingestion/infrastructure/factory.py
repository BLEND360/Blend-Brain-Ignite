"""Composition helpers for local document ingestion."""

from blend_brain.document_ingestion.application import DocumentIngestionService
from blend_brain.document_ingestion.infrastructure.detection import ContentAwareFormatDetector
from blend_brain.document_ingestion.infrastructure.filesystem import (
    FileSystemSourceLoader,
    IngestionLimits,
)
from blend_brain.document_ingestion.infrastructure.parsers import (
    DocxParser,
    MarkdownParser,
    PdfParser,
    PptxParser,
    TextParser,
)


def create_local_ingestion_service(
    limits: IngestionLimits | None = None,
) -> DocumentIngestionService:
    """Compose the Phase 2 local-filesystem ingestion workflow."""
    resolved_limits = limits or IngestionLimits()
    return DocumentIngestionService(
        loader=FileSystemSourceLoader(resolved_limits),
        detector=ContentAwareFormatDetector(resolved_limits),
        parsers=(
            PptxParser(),
            DocxParser(),
            PdfParser(resolved_limits),
            MarkdownParser(),
            TextParser(),
        ),
    )
