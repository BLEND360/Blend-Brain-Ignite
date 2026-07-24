"""Stable failures raised by the ingestion bounded context."""

from __future__ import annotations

from typing import Any


class IngestionError(Exception):
    """Base class carrying a machine-readable ingestion failure code."""

    code = "ingestion_failed"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class DocumentAccessError(IngestionError):
    """The source cannot be safely read."""

    code = "document_access_failed"


class DocumentTooLargeError(IngestionError):
    """A configured resource limit was exceeded."""

    code = "document_too_large"


class UnsupportedDocumentError(IngestionError):
    """The source format is unsupported."""

    code = "unsupported_document"


class InvalidDocumentError(IngestionError):
    """The source content does not match its declared format."""

    code = "invalid_document"


class CorruptDocumentError(IngestionError):
    """A recognized source cannot be parsed."""

    code = "corrupt_document"


class EncryptedDocumentError(IngestionError):
    """A password-protected source cannot be processed."""

    code = "encrypted_document"


class EmptyDocumentError(IngestionError):
    """A source contains no extractable text."""

    code = "empty_document"
