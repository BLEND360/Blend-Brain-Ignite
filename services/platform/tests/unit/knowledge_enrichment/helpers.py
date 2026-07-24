"""Typed Phase 3 test data builders."""

from __future__ import annotations

from datetime import UTC, datetime

from blend_brain.document_ingestion.domain import (
    DocumentFormat,
    DocumentMetadata,
    DocumentSection,
    ExtractedDocument,
    SectionKind,
    SectionLocator,
)
from blend_brain.knowledge_enrichment.domain import (
    ClaimConfidence,
    DocumentProfile,
    EmbeddingRecord,
    EmbeddingTargetType,
    EnrichmentBundle,
    EvidenceReference,
    GroundedClaim,
    ProjectDNA,
)

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def document() -> ExtractedDocument:
    """Return a representative citation-ready document."""
    return ExtractedDocument(
        source_id="file:///knowledge/project.md",
        filename="project.md",
        document_format=DocumentFormat.MARKDOWN,
        size_bytes=120,
        sha256="a" * 64,
        sections=(
            DocumentSection(
                sequence=1,
                kind=SectionKind.HEADING,
                text=(
                    "Retail Forecasting\nBlend built a demand forecasting platform for Example Co."
                ),
                locator=SectionLocator(heading="Retail Forecasting"),
            ),
            DocumentSection(
                sequence=2,
                kind=SectionKind.BODY,
                text="The solution used Snowflake and AWS and reduced planning time by 30%.",
            ),
        ),
        metadata=DocumentMetadata(title="Retail Forecasting", author="Blend", created_at=NOW),
    )


def profile() -> DocumentProfile:
    """Return metadata aligned to the representative document."""
    return DocumentProfile(
        document_id="document-id",
        source_id="file:///knowledge/project.md",
        filename="project.md",
        document_format="markdown",
        sha256="a" * 64,
        size_bytes=120,
        title="Retail Forecasting",
        author="Blend",
        subject=None,
        created_at=NOW,
        modified_at=None,
        section_count=2,
        character_count=140,
        word_count=22,
    )


def claim(value: str = "Retail Forecasting") -> GroundedClaim:
    """Return one grounded claim."""
    return GroundedClaim(
        value=value,
        confidence=ClaimConfidence.HIGH,
        evidence=(EvidenceReference(1, "Retail Forecasting"),),
    )


def dna() -> ProjectDNA:
    """Return a minimal valid Project DNA aggregate."""
    return ProjectDNA(
        dna_id="dna-id",
        project_id="project-1",
        document_id="document-id",
        version=1,
        project_name=claim(),
        client_name=None,
        industry=None,
        engagement_type=None,
        summary=claim("demand forecasting platform"),
        business_challenges=(),
        use_cases=(claim("demand forecasting"),),
        capabilities=(),
        technologies=(claim("Snowflake"),),
        data_sources=(),
        cloud_platforms=(claim("AWS"),),
        outcomes=(claim("reduced planning time by 30%"),),
        differentiators=(),
        experts=(),
        model="gpt-4.1-2025-04-14",
        prompt_version="project-dna-v1",
        generated_at=NOW,
    )


def bundle(*, dimensions: int = 3072, include_embedding: bool = True) -> EnrichmentBundle:
    """Return a complete persistence bundle."""
    embeddings = (
        (
            EmbeddingRecord(
                embedding_id="embedding-id",
                project_id="project-1",
                document_id="document-id",
                target_type=EmbeddingTargetType.DOCUMENT_SECTION,
                target_id="document-id:section:1",
                section_sequence=1,
                content_sha256="b" * 64,
                model="text-embedding-3-large",
                dimensions=dimensions,
                vector=tuple(0.1 for _ in range(dimensions)),
                created_at=NOW,
            ),
        )
        if include_embedding
        else ()
    )
    return EnrichmentBundle(
        run_id="run-id",
        project_id="project-1",
        document=document(),
        profile=profile(),
        project_dna=dna(),
        embeddings=embeddings,
        completed_at=NOW,
    )
