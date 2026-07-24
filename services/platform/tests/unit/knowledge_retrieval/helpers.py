"""Typed Phase 4 test builders."""

from blend_brain.knowledge_retrieval.domain import IndexedSection, RetrievalHit


def section(
    section_id: str = "section-1",
    *,
    text: str = "Snowflake reduced planning time by 30%.",
    embedding: tuple[float, ...] = (1.0, 0.0, 0.0),
    document_id: str = "document-1",
    project_id: str = "project-1",
) -> IndexedSection:
    """Return a representative indexed section."""
    return IndexedSection(
        section_id=section_id,
        project_id=project_id,
        document_id=document_id,
        filename=f"{document_id}.md",
        sequence=1,
        kind="body",
        text=text,
        embedding=embedding,
        heading="Outcome",
    )


def hit(
    source_id: str = "S1",
    *,
    item: IndexedSection | None = None,
    dense_score: float | None = 0.9,
    lexical_score: float | None = 2.0,
) -> RetrievalHit:
    """Return one fused result."""
    return RetrievalHit(
        source_id=source_id,
        section=item or section(),
        fusion_score=0.02,
        dense_score=dense_score,
        lexical_score=lexical_score,
        dense_rank=1 if dense_score is not None else None,
        lexical_rank=1 if lexical_score is not None else None,
    )
