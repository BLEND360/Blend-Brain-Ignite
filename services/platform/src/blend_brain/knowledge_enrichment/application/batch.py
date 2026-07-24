"""Resumable batch orchestration for local document enrichment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from blend_brain.document_ingestion.domain import IngestionError
from blend_brain.knowledge_enrichment.application.metadata import MetadataExtractionService
from blend_brain.knowledge_enrichment.domain import EnrichmentError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from blend_brain.document_ingestion.domain import ExtractedDocument
    from blend_brain.knowledge_enrichment.domain import EnrichmentBundle


@dataclass(frozen=True, slots=True)
class BatchDocument:
    """One source and its stable project identity."""

    source_id: str
    project_id: str


@dataclass(frozen=True, slots=True)
class BatchFailure:
    """Safe diagnostic for one source that could not be completed."""

    source_id: str
    project_id: str
    code: str
    message: str
    context: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Terminal counts and failures for one batch invocation."""

    discovered: int
    completed: int
    skipped: int
    failures: tuple[BatchFailure, ...]


class DocumentExtractor(Protocol):
    """Extract one local document."""

    def ingest(self, source_id: str) -> ExtractedDocument:
        """Return normalized document content."""
        ...


class DocumentEnricher(Protocol):
    """Enrich and persist one extracted document."""

    def enrich(self, project_id: str, document: ExtractedDocument) -> EnrichmentBundle:
        """Persist one complete enrichment bundle."""
        ...


class DatasetIngestionService:
    """Process independent documents while preserving resumability."""

    def __init__(
        self,
        extractor: DocumentExtractor,
        enricher: DocumentEnricher,
        *,
        metadata_extractor: MetadataExtractionService | None = None,
    ) -> None:
        self._extractor = extractor
        self._enricher = enricher
        self._metadata_extractor = metadata_extractor or MetadataExtractionService()

    def run(
        self,
        documents: Iterable[BatchDocument],
        *,
        completed_document_ids: frozenset[str] = frozenset(),
        max_workers: int = 1,
        progress: Callable[[int, int, str, BatchDocument], None] | None = None,
    ) -> BatchResult:
        """Process a bounded snapshot, skipping already completed document versions."""
        if not 1 <= max_workers <= 16:
            raise ValueError("max_workers must be between 1 and 16")
        candidates = tuple(documents)
        completed = 0
        skipped = 0
        failures: list[BatchFailure] = []
        total = len(candidates)
        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="enrichment"
        ) as executor:
            outcomes = executor.map(
                lambda candidate: self._process(candidate, completed_document_ids),
                candidates,
            )
            for index, (candidate, outcome) in enumerate(
                zip(candidates, outcomes, strict=True), start=1
            ):
                status, failure = outcome
                if status == "completed":
                    completed += 1
                elif status == "skipped":
                    skipped += 1
                if failure is not None:
                    failures.append(failure)
                if progress is not None:
                    progress(index, total, status, candidate)
        return BatchResult(total, completed, skipped, tuple(failures))

    def _process(
        self,
        candidate: BatchDocument,
        completed_document_ids: frozenset[str],
    ) -> tuple[str, BatchFailure | None]:
        try:
            document = self._extractor.ingest(candidate.source_id)
            profile = self._metadata_extractor.extract(document)
            if profile.document_id in completed_document_ids:
                return "skipped", None
            self._enricher.enrich(candidate.project_id, document)
        except (IngestionError, EnrichmentError) as exception:
            return "failed", BatchFailure(
                source_id=candidate.source_id,
                project_id=candidate.project_id,
                code=exception.code,
                message=str(exception),
                context=tuple(
                    sorted((key, str(value)) for key, value in exception.context.items())
                ),
            )
        return "completed", None
