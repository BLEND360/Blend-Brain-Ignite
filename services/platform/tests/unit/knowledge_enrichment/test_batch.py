"""Resumable dataset-ingestion orchestration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blend_brain.document_ingestion.domain import CorruptDocumentError
from blend_brain.knowledge_enrichment.application import (
    BatchDocument,
    DatasetIngestionService,
    MetadataExtractionService,
)
from blend_brain.knowledge_enrichment.domain import PersistenceError
from tests.unit.knowledge_enrichment.helpers import document

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import ExtractedDocument
    from blend_brain.knowledge_enrichment.domain import EnrichmentBundle


class Extractor:
    """Return a document or a stable ingestion failure by source ID."""

    def ingest(self, source_id: str) -> ExtractedDocument:
        if source_id == "corrupt.pptx":
            raise CorruptDocumentError("document is corrupt")
        return document()


class Enricher:
    """Record projects and optionally fail persistence."""

    def __init__(self) -> None:
        self.projects: list[str] = []

    def enrich(self, project_id: str, _document: ExtractedDocument) -> EnrichmentBundle:
        if project_id == "persistence-failure":
            raise PersistenceError("database unavailable")
        self.projects.append(project_id)
        return None  # type: ignore[return-value]


def test_batch_completes_skips_and_isolates_known_failures() -> None:
    source = document()
    completed_id = MetadataExtractionService().extract(source).document_id
    enricher = Enricher()
    progress: list[tuple[int, int, str]] = []
    candidates = (
        BatchDocument("already-done.pptx", "completed-project"),
        BatchDocument("valid.pptx", "new-project"),
        BatchDocument("corrupt.pptx", "corrupt-project"),
        BatchDocument("valid-2.pptx", "persistence-failure"),
    )

    result = DatasetIngestionService(Extractor(), enricher).run(
        candidates,
        completed_document_ids=frozenset({completed_id}),
        progress=lambda index, total, status, _candidate: progress.append((index, total, status)),
    )

    assert result.discovered == 4
    assert result.completed == 0
    assert result.skipped == 3
    assert len(result.failures) == 1
    assert result.failures[0].code == "corrupt_document"
    assert progress[-1] == (4, 4, "skipped")


def test_batch_records_enrichment_failure_when_document_is_not_completed() -> None:
    result = DatasetIngestionService(Extractor(), Enricher()).run(
        (BatchDocument("valid.pptx", "persistence-failure"),)
    )

    assert result.completed == 0
    assert result.skipped == 0
    assert result.failures[0].code == "enrichment_persistence_failed"


def test_batch_supports_bounded_concurrent_processing() -> None:
    enricher = Enricher()
    result = DatasetIngestionService(Extractor(), enricher).run(
        (BatchDocument("one.pptx", "project-1"), BatchDocument("two.pptx", "project-2")),
        max_workers=2,
    )

    assert result.completed == 2
    assert set(enricher.projects) == {"project-1", "project-2"}

    with pytest.raises(ValueError, match="between 1 and 16"):
        DatasetIngestionService(Extractor(), enricher).run((), max_workers=17)
