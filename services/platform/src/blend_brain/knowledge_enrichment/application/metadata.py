"""Deterministic document metadata extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from blend_brain.knowledge_enrichment.domain import DocumentProfile

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import ExtractedDocument


class MetadataExtractionService:
    """Create stable metadata without model calls or mutable state."""

    def extract(self, document: ExtractedDocument) -> DocumentProfile:
        """Calculate identity and content statistics for a document version."""
        document_id = str(uuid5(NAMESPACE_URL, f"{document.source_id}:{document.sha256}"))
        text = document.text
        return DocumentProfile(
            document_id=document_id,
            source_id=document.source_id,
            filename=document.filename,
            document_format=document.document_format.value,
            sha256=document.sha256,
            size_bytes=document.size_bytes,
            title=document.metadata.title,
            author=document.metadata.author,
            subject=document.metadata.subject,
            created_at=document.metadata.created_at,
            modified_at=document.metadata.modified_at,
            section_count=len(document.sections),
            character_count=len(text),
            word_count=len(text.split()),
        )
