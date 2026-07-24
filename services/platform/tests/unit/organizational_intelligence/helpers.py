"""Typed Phase 6 test builders."""

from blend_brain.organizational_intelligence.domain import (
    ExpertAssociation,
    GraphEvidence,
    ProjectIntelligenceRecord,
)


def record(
    project_id: str = "project-1",
    *,
    name: str = "Retail Forecasting",
    embedding: tuple[float, ...] = (1.0, 0.0, 0.0),
    technologies: tuple[str, ...] = ("Snowflake",),
    industries: tuple[str, ...] = ("Retail",),
    expert_name: str | None = "Jane Expert",
) -> ProjectIntelligenceRecord:
    """Return one project intelligence record."""
    experts = (
        (
            ExpertAssociation(
                expert_id=f"expert-{expert_name.casefold().replace(' ', '-')}"
                if expert_name
                else "",
                name=expert_name or "",
                evidence=(GraphEvidence("document-1", 2, f"{expert_name} led delivery"),),
            ),
        )
        if expert_name
        else ()
    )
    return ProjectIntelligenceRecord(
        project_id=project_id,
        dna_id=f"dna-{project_id}",
        display_name=name,
        embedding=embedding,
        industries=industries,
        use_cases=("Demand forecasting",),
        capabilities=("Predictive analytics",),
        technologies=technologies,
        cloud_platforms=("AWS",),
        experts=experts,
    )
