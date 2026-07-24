"""Plain-text parser adapter."""

from __future__ import annotations

from charset_normalizer import from_bytes

from blend_brain.document_ingestion.domain import (
    CorruptDocumentError,
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    DocumentSource,
    ExtractedDocument,
    SectionKind,
)
from blend_brain.document_ingestion.infrastructure.parsers.common import build_document


def decode_text(content: bytes, filename: str) -> tuple[str, str]:
    """Decode text deterministically and report the selected character encoding."""
    if not content:
        return "", "utf-8"
    try:
        return content.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        if len(content) < 64:
            try:
                return content.decode("cp1252"), "windows-1252"
            except UnicodeDecodeError:
                pass
        match = from_bytes(content).best()
        if match is None or match.encoding is None:
            raise CorruptDocumentError(
                "Text encoding could not be determined",
                filename=filename,
            ) from None
        return str(match), match.encoding.lower()


class TextParser:
    """Extract Unicode content from TXT files."""

    @property
    def document_format(self) -> DocumentFormat:
        """Return the supported format."""
        return DocumentFormat.TEXT

    def parse(self, source: DocumentSource) -> ExtractedDocument:
        """Decode one text document into a citable body section."""
        text, encoding = decode_text(source.content, source.filename)
        return build_document(
            source,
            self.document_format,
            [DocumentSection(sequence=1, kind=SectionKind.BODY, text=text)],
            metadata=DocumentMetadata(extra=(("encoding", encoding),)),
        )
