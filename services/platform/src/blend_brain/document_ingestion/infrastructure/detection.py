"""Content-aware document format validation."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import BadZipFile, ZipFile, is_zipfile

from blend_brain.document_ingestion.domain import (
    DocumentFormat,
    DocumentSource,
    DocumentTooLargeError,
    InvalidDocumentError,
    UnsupportedDocumentError,
)
from blend_brain.document_ingestion.infrastructure.filesystem import IngestionLimits

if TYPE_CHECKING:
    from zipfile import ZipInfo

_SUFFIX_FORMATS = {
    ".pptx": DocumentFormat.PPTX,
    ".docx": DocumentFormat.DOCX,
    ".pdf": DocumentFormat.PDF,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
    ".txt": DocumentFormat.TEXT,
}


class ContentAwareFormatDetector:
    """Verify extensions against container signatures and structure."""

    def __init__(self, limits: IngestionLimits | None = None) -> None:
        self._limits = limits or IngestionLimits()

    def detect(self, source: DocumentSource) -> DocumentFormat:
        """Return a verified format or reject misleading content."""
        suffix = self._suffix(source.filename)
        expected = _SUFFIX_FORMATS.get(suffix)
        if expected is None:
            raise UnsupportedDocumentError(
                "Document extension is not supported",
                filename=source.filename,
                extension=suffix,
            )

        if expected in {DocumentFormat.PPTX, DocumentFormat.DOCX}:
            actual = self._detect_office_format(source)
            if actual is not expected:
                raise InvalidDocumentError(
                    "Office document content does not match its extension",
                    filename=source.filename,
                    expected=expected.value,
                    detected=actual.value,
                )
        elif expected is DocumentFormat.PDF and b"%PDF-" not in source.content[:1024]:
            raise InvalidDocumentError(
                "PDF signature was not found",
                filename=source.filename,
            )
        elif (
            expected in {DocumentFormat.MARKDOWN, DocumentFormat.TEXT} and b"\x00" in source.content
        ):
            raise InvalidDocumentError(
                "Text document contains binary null bytes",
                filename=source.filename,
            )
        return expected

    def _detect_office_format(self, source: DocumentSource) -> DocumentFormat:
        stream = BytesIO(source.content)
        if not is_zipfile(stream):
            raise InvalidDocumentError(
                "Office document is not a valid Open XML container",
                filename=source.filename,
            )
        try:
            with ZipFile(stream) as archive:
                entries = archive.infolist()
                self._validate_archive(entries, source.filename)
                names = {entry.filename for entry in entries}
        except BadZipFile as exception:
            raise InvalidDocumentError(
                "Office document container is corrupt",
                filename=source.filename,
            ) from exception

        if "ppt/presentation.xml" in names:
            return DocumentFormat.PPTX
        if "word/document.xml" in names:
            return DocumentFormat.DOCX
        raise InvalidDocumentError(
            "Open XML container is not a supported PowerPoint or Word document",
            filename=source.filename,
        )

    def _validate_archive(self, entries: list[ZipInfo], filename: str) -> None:
        if len(entries) > self._limits.max_archive_entries:
            raise DocumentTooLargeError(
                "Office document contains too many archive entries",
                filename=filename,
                entry_count=len(entries),
            )
        total_uncompressed = sum(entry.file_size for entry in entries)
        if total_uncompressed > self._limits.max_archive_uncompressed_bytes:
            raise DocumentTooLargeError(
                "Office document expands beyond the configured archive limit",
                filename=filename,
                uncompressed_bytes=total_uncompressed,
            )
        for entry in entries:
            if entry.flag_bits & 0x1:
                raise InvalidDocumentError(
                    "Encrypted Office archive entries are not supported",
                    filename=filename,
                )
            if entry.file_size == 0:
                continue
            ratio = entry.file_size / max(entry.compress_size, 1)
            if ratio > self._limits.max_archive_compression_ratio:
                raise DocumentTooLargeError(
                    "Office document contains a suspicious compression ratio",
                    filename=filename,
                    entry=entry.filename,
                )

    @staticmethod
    def _suffix(filename: str) -> str:
        dot = filename.rfind(".")
        return filename[dot:].lower() if dot >= 0 else ""
