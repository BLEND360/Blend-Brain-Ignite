"""Format-specific extraction tests using real documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blend_brain.document_ingestion.domain import (
    CorruptDocumentError,
    DocumentFormat,
    DocumentTooLargeError,
    EmptyDocumentError,
    EncryptedDocumentError,
    SectionKind,
)
from blend_brain.document_ingestion.infrastructure.filesystem import IngestionLimits
from blend_brain.document_ingestion.infrastructure.parsers import (
    DocxParser,
    MarkdownParser,
    PdfParser,
    PptxParser,
    TextParser,
)
from tests.unit.document_ingestion.helpers import make_docx, make_pdf, make_pptx, source

if TYPE_CHECKING:
    from blend_brain.document_ingestion.application import DocumentParser


def test_extracts_pptx_slides_tables_notes_and_metadata() -> None:
    document = PptxParser().parse(source("project.pptx", make_pptx()))

    assert document.document_format is DocumentFormat.PPTX
    assert document.metadata.title == "Project Deck"
    assert len(document.sections) == 1
    assert document.sections[0].kind is SectionKind.SLIDE
    assert document.sections[0].locator.slide_number == 1
    assert "Architecture" in document.text
    assert "Layer | Owner" in document.text
    assert "Discuss security limits" in document.text


def test_extracts_docx_headings_tables_and_metadata() -> None:
    document = DocxParser().parse(source("project.docx", make_docx()))

    assert document.document_format is DocumentFormat.DOCX
    assert document.metadata.title == "Word Project"
    assert document.sections[0].locator.heading == "Executive summary"
    assert "Client | Industry" in document.text
    assert "Example Co | Retail" in document.text


def test_extracts_pdf_pages_metadata_and_ocr_warning() -> None:
    document = PdfParser().parse(source("project.pdf", make_pdf(include_blank_page=True)))

    assert document.document_format is DocumentFormat.PDF
    assert document.metadata.title == "PDF Project"
    assert document.sections[0].locator.page_number == 1
    assert "Project knowledge" in document.text
    assert document.warnings[0].code == "page_has_no_extractable_text"
    assert document.warnings[0].locator == document.sections[1].locator


def test_pdf_rejects_encryption_and_page_limit() -> None:
    with pytest.raises(EncryptedDocumentError):
        PdfParser().parse(source("secret.pdf", make_pdf(encrypted=True)))

    limits = IngestionLimits(max_pdf_pages=1)
    with pytest.raises(DocumentTooLargeError):
        PdfParser(limits).parse(source("large.pdf", make_pdf(include_blank_page=True)))


def test_markdown_preserves_preamble_and_heading_boundaries() -> None:
    content = b"Preamble\n\n# Overview\nFirst section\n## Results ##\nSecond section"
    document = MarkdownParser().parse(source("project.md", content))

    assert len(document.sections) == 3
    assert document.sections[0].kind is SectionKind.BODY
    assert document.sections[1].locator.heading == "Overview"
    assert document.sections[2].locator.heading == "Results"
    assert document.sections[2].text == "Results\nSecond section"


def test_text_decodes_utf8_bom_and_legacy_encoding() -> None:
    utf8 = TextParser().parse(source("utf8.txt", b"\xef\xbb\xbfBlend knowledge"))
    legacy = TextParser().parse(source("legacy.txt", "caf\xe9".encode("cp1252")))

    assert utf8.text == "Blend knowledge"
    assert utf8.metadata.extra == (("encoding", "utf-8"),)
    assert legacy.text == "caf\xe9"
    assert legacy.metadata.extra[0][0] == "encoding"


@pytest.mark.parametrize(
    ("parser", "filename"),
    [
        (TextParser(), "empty.txt"),
        (MarkdownParser(), "empty.md"),
    ],
)
def test_empty_textual_documents_are_rejected(parser: DocumentParser, filename: str) -> None:
    with pytest.raises(EmptyDocumentError):
        parser.parse(source(filename, b"  \n"))


@pytest.mark.parametrize(
    "parser",
    [PptxParser(), DocxParser(), PdfParser()],
)
def test_binary_parsers_translate_corrupt_input(parser: DocumentParser) -> None:
    with pytest.raises(CorruptDocumentError):
        parser.parse(source(f"broken.{parser.document_format.value}", b"invalid"))
