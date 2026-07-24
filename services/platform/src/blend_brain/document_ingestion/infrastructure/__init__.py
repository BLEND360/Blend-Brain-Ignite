"""Infrastructure adapters for document ingestion."""

from blend_brain.document_ingestion.infrastructure.factory import (
    create_local_ingestion_service,
)
from blend_brain.document_ingestion.infrastructure.filesystem import (
    FileSystemDocumentScanner,
    FileSystemSourceLoader,
    IngestionLimits,
)

__all__ = [
    "FileSystemDocumentScanner",
    "FileSystemSourceLoader",
    "IngestionLimits",
    "create_local_ingestion_service",
]
