"""Stable embedding-target construction."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from blend_brain.knowledge_enrichment.domain import (
    DocumentProfile,
    EmbeddingTarget,
    EmbeddingTargetType,
    ProjectDNA,
)

if TYPE_CHECKING:
    from blend_brain.document_ingestion.domain import ExtractedDocument


class EmbeddingTargetFactory:
    """Build idempotent section and Project DNA embedding targets."""

    def create(
        self,
        project_id: str,
        profile: DocumentProfile,
        document: ExtractedDocument,
        project_dna: ProjectDNA,
    ) -> tuple[EmbeddingTarget, ...]:
        """Return ordered non-empty targets with content-addressed identities."""
        targets: list[EmbeddingTarget] = []
        for section in document.sections:
            text = section.text.strip()
            if not text:
                continue
            target_id = f"{profile.document_id}:section:{section.sequence}"
            targets.append(
                self._target(
                    project_id=project_id,
                    document_id=profile.document_id,
                    target_type=EmbeddingTargetType.DOCUMENT_SECTION,
                    target_id=target_id,
                    section_sequence=section.sequence,
                    text=text,
                )
            )
        dna_text = project_dna.embedding_text().strip()
        if dna_text:
            targets.append(
                self._target(
                    project_id=project_id,
                    document_id=profile.document_id,
                    target_type=EmbeddingTargetType.PROJECT_DNA,
                    target_id=project_dna.dna_id,
                    section_sequence=None,
                    text=dna_text,
                )
            )
        return tuple(targets)

    @staticmethod
    def _target(
        *,
        project_id: str,
        document_id: str,
        target_type: EmbeddingTargetType,
        target_id: str,
        section_sequence: int | None,
        text: str,
    ) -> EmbeddingTarget:
        content_sha256 = sha256(text.encode()).hexdigest()
        embedding_id = str(uuid5(NAMESPACE_URL, f"{target_id}:{content_sha256}"))
        return EmbeddingTarget(
            embedding_id=embedding_id,
            project_id=project_id,
            document_id=document_id,
            target_type=target_type,
            target_id=target_id,
            section_sequence=section_sequence,
            content_sha256=content_sha256,
            text=text,
        )
