"""Domain contracts for document ingestion."""

from blend_brain.document_ingestion.domain.errors import (
    CorruptDocumentError,
    DocumentAccessError,
    DocumentTooLargeError,
    EmptyDocumentError,
    EncryptedDocumentError,
    IngestionError,
    InvalidDocumentError,
    UnsupportedDocumentError,
)
from blend_brain.document_ingestion.domain.models import (
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    DocumentSource,
    ExtractedDocument,
    ExtractionWarning,
    SectionKind,
    SectionLocator,
)

__all__ = [
    "CorruptDocumentError",
    "DocumentAccessError",
    "DocumentFormat",
    "DocumentMetadata",
    "DocumentSection",
    "DocumentSource",
    "DocumentTooLargeError",
    "EmptyDocumentError",
    "EncryptedDocumentError",
    "ExtractedDocument",
    "ExtractionWarning",
    "IngestionError",
    "InvalidDocumentError",
    "SectionKind",
    "SectionLocator",
    "UnsupportedDocumentError",
]
