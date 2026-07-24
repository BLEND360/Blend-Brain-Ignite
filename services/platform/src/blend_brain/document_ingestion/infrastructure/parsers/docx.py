"""Word Open XML parser adapter."""

from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from blend_brain.document_ingestion.domain import (
    CorruptDocumentError,
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    DocumentSource,
    ExtractedDocument,
    SectionKind,
    SectionLocator,
)
from blend_brain.document_ingestion.infrastructure.parsers.common import (
    build_document,
    normalize_datetime,
    optional_text,
)


class DocxParser:
    """Extract paragraphs and tables in Word document order."""

    @property
    def document_format(self) -> DocumentFormat:
        """Return the supported format."""
        return DocumentFormat.DOCX

    def parse(self, source: DocumentSource) -> ExtractedDocument:
        """Group Word content into heading-addressable sections."""
        try:
            document = Document(BytesIO(source.content))
            sections: list[DocumentSection] = []
            heading: str | None = None
            lines: list[str] = []

            def flush() -> None:
                if not lines and heading is None:
                    return
                text = "\n".join(lines)
                if heading:
                    text = f"{heading}\n{text}"
                sections.append(
                    DocumentSection(
                        sequence=len(sections) + 1,
                        kind=SectionKind.HEADING if heading else SectionKind.BODY,
                        text=text,
                        locator=SectionLocator(heading=heading),
                    )
                )

            for block in document.iter_inner_content():
                if isinstance(block, Paragraph):
                    style_name = block.style.name if block.style is not None else ""
                    if style_name.casefold().startswith("heading") and block.text.strip():
                        flush()
                        heading = block.text.strip()
                        lines = []
                    elif block.text.strip():
                        lines.append(block.text)
                elif isinstance(block, Table):
                    lines.extend(self._table_lines(block))
            flush()
            properties = document.core_properties
            metadata = DocumentMetadata(
                title=optional_text(properties.title),
                author=optional_text(properties.author),
                subject=optional_text(properties.subject),
                created_at=normalize_datetime(properties.created),
                modified_at=normalize_datetime(properties.modified),
            )
            return build_document(source, self.document_format, sections, metadata=metadata)
        except (BadZipFile, ValueError, KeyError, TypeError) as exception:
            raise CorruptDocumentError(
                "Word document could not be parsed",
                filename=source.filename,
            ) from exception

    @staticmethod
    def _table_lines(table: Table) -> list[str]:
        return [
            " | ".join(cell.text.strip() for cell in row.cells)
            for row in table.rows
            if any(cell.text.strip() for cell in row.cells)
        ]
