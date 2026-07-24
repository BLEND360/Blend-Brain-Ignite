"""Markdown parser preserving heading-level citation boundaries."""

from __future__ import annotations

import re

from blend_brain.document_ingestion.domain import (
    DocumentFormat,
    DocumentSection,
    DocumentSource,
    ExtractedDocument,
    SectionKind,
    SectionLocator,
)
from blend_brain.document_ingestion.infrastructure.parsers.common import build_document
from blend_brain.document_ingestion.infrastructure.parsers.text import decode_text

_ATX_HEADING = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$")


class MarkdownParser:
    """Split Markdown at ATX headings while preserving source text."""

    @property
    def document_format(self) -> DocumentFormat:
        """Return the supported format."""
        return DocumentFormat.MARKDOWN

    def parse(self, source: DocumentSource) -> ExtractedDocument:
        """Extract ordered preamble and heading sections."""
        text, _encoding = decode_text(source.content, source.filename)
        sections: list[DocumentSection] = []
        current_heading: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            if not current_lines and current_heading is None:
                return
            section_text = "\n".join(current_lines)
            if current_heading is not None:
                section_text = f"{current_heading}\n{section_text}"
            sections.append(
                DocumentSection(
                    sequence=len(sections) + 1,
                    kind=SectionKind.HEADING if current_heading else SectionKind.BODY,
                    text=section_text,
                    locator=SectionLocator(heading=current_heading),
                )
            )

        for line in text.splitlines():
            match = _ATX_HEADING.match(line)
            if match is None:
                current_lines.append(line)
                continue
            flush()
            current_heading = match.group("title").strip()
            current_lines = []
        flush()
        return build_document(source, self.document_format, sections)
