"""Ingestion orchestration, detection, and filesystem tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blend_brain.document_ingestion.application import DocumentIngestionService
from blend_brain.document_ingestion.domain import (
    DocumentAccessError,
    DocumentFormat,
    DocumentSource,
    DocumentTooLargeError,
    InvalidDocumentError,
    UnsupportedDocumentError,
)
from blend_brain.document_ingestion.infrastructure import (
    FileSystemDocumentScanner,
    FileSystemSourceLoader,
    IngestionLimits,
    create_local_ingestion_service,
)
from blend_brain.document_ingestion.infrastructure.detection import ContentAwareFormatDetector
from blend_brain.document_ingestion.infrastructure.parsers import TextParser
from tests.unit.document_ingestion.helpers import make_docx, make_pdf, make_pptx, source, write

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.parametrize(
    ("filename", "content", "expected_format"),
    [
        ("project.pptx", make_pptx(), DocumentFormat.PPTX),
        ("project.docx", make_docx(), DocumentFormat.DOCX),
        ("project.pdf", make_pdf(), DocumentFormat.PDF),
        ("project.md", b"# Knowledge\nReusable", DocumentFormat.MARKDOWN),
        ("project.markdown", b"# Knowledge\nReusable", DocumentFormat.MARKDOWN),
        ("project.txt", b"Reusable knowledge", DocumentFormat.TEXT),
    ],
)
def test_detects_supported_content(
    filename: str,
    content: bytes,
    expected_format: DocumentFormat,
) -> None:
    assert ContentAwareFormatDetector().detect(source(filename, content)) is expected_format


def test_rejects_unsupported_mismatched_and_binary_sources() -> None:
    detector = ContentAwareFormatDetector()

    with pytest.raises(UnsupportedDocumentError):
        detector.detect(source("project.xlsx", b"data"))
    with pytest.raises(InvalidDocumentError):
        detector.detect(source("project.docx", make_pptx()))
    with pytest.raises(InvalidDocumentError):
        detector.detect(source("project.pdf", b"not a PDF"))
    with pytest.raises(InvalidDocumentError):
        detector.detect(source("project.txt", b"binary\x00content"))


def test_local_service_ingests_every_supported_format(tmp_path: Path) -> None:
    documents = (
        write(tmp_path / "project.pptx", make_pptx()),
        write(tmp_path / "project.docx", make_docx()),
        write(tmp_path / "project.pdf", make_pdf()),
        write(tmp_path / "project.md", b"# Summary\nMarkdown knowledge"),
        write(tmp_path / "project.txt", b"Text knowledge"),
    )
    service = create_local_ingestion_service()

    results = tuple(service.ingest(str(path)) for path in documents)

    assert {result.document_format for result in results} == set(DocumentFormat)
    assert all(result.sha256 and result.text for result in results)


def test_loader_enforces_file_resource_and_access_rules(tmp_path: Path) -> None:
    path = write(tmp_path / "large.txt", b"12345")
    with pytest.raises(DocumentTooLargeError):
        FileSystemSourceLoader(IngestionLimits(max_file_size_bytes=4)).load(str(path))
    with pytest.raises(DocumentAccessError):
        FileSystemSourceLoader().load(str(tmp_path / "missing.txt"))
    with pytest.raises(DocumentAccessError):
        FileSystemSourceLoader().load(str(tmp_path))


def test_scanner_is_filtered_deterministic_and_hidden_aware(tmp_path: Path) -> None:
    write(tmp_path / "b.txt", b"b")
    write(tmp_path / "A.md", b"a")
    write(tmp_path / "ignored.csv", b"ignored")
    hidden = tmp_path / ".private"
    hidden.mkdir()
    write(hidden / "secret.txt", b"secret")

    visible = FileSystemDocumentScanner().discover(tmp_path)
    all_documents = FileSystemDocumentScanner(include_hidden=True).discover(tmp_path)

    assert [path.name for path in visible] == ["A.md", "b.txt"]
    assert len(all_documents) == 3
    with pytest.raises(DocumentAccessError):
        FileSystemDocumentScanner().discover(tmp_path / "missing")


def test_service_rejects_duplicate_or_missing_parser() -> None:
    loader = FileSystemSourceLoader()
    detector = ContentAwareFormatDetector()

    with pytest.raises(ValueError, match="Duplicate parser"):
        DocumentIngestionService(loader, detector, (TextParser(), TextParser()))
    text = source("project.txt", b"knowledge")

    class MemoryLoader:
        def load(self, _source_id: str) -> DocumentSource:
            return text

    with pytest.raises(UnsupportedDocumentError):
        DocumentIngestionService(MemoryLoader(), detector, ()).ingest("memory")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: IngestionLimits(max_file_size_bytes=0),
        lambda: IngestionLimits(max_archive_entries=0),
        lambda: IngestionLimits(max_archive_compression_ratio=0.5),
    ],
)
def test_invalid_limits_are_rejected(factory: Callable[[], IngestionLimits]) -> None:
    with pytest.raises(ValueError, match="must be"):
        factory()
