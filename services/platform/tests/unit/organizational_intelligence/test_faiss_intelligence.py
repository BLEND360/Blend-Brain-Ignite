"""Project similarity and Expert Finder ranking tests."""

import pytest

from blend_brain.organizational_intelligence.domain import (
    NodeType,
    ProjectIntelligenceRecord,
    ProjectNotFoundError,
)
from blend_brain.organizational_intelligence.infrastructure.faiss_intelligence import (
    FaissIntelligenceIndexFactory,
)
from tests.unit.organizational_intelligence.helpers import record


def corpus() -> tuple[ProjectIntelligenceRecord, ...]:
    """Return a representative project corpus."""
    return (
        record(),
        record(
            "project-2",
            name="Retail Planning",
            embedding=(0.95, 0.05, 0.0),
            expert_name="Jane Expert",
        ),
        record(
            "project-3",
            name="Healthcare Migration",
            embedding=(0.0, 1.0, 0.0),
            technologies=("Databricks",),
            industries=("Healthcare",),
            expert_name="Alex Expert",
        ),
    )


def test_similarity_ranks_vectors_and_explains_shared_graph_signals() -> None:
    index = FaissIntelligenceIndexFactory(minimum_similarity=0.5).build(corpus())

    results = index.similar_projects("project-1", limit=2)

    assert results[0].project_id == "project-2"
    assert results[0].score > 0.9
    assert any(signal.kind is NodeType.TECHNOLOGY for signal in results[0].shared_signals)
    assert all(result.project_id != "project-1" for result in results)


def test_similarity_rejects_unknown_project_and_invalid_limit() -> None:
    index = FaissIntelligenceIndexFactory().build(corpus())
    with pytest.raises(ProjectNotFoundError):
        index.similar_projects("not-allowed", limit=3)
    with pytest.raises(ValueError, match="limit"):
        index.similar_projects("project-1", limit=0)


def test_expert_finder_aggregates_projects_evidence_and_exact_signals() -> None:
    index = FaissIntelligenceIndexFactory(minimum_expert_score=0.2).build(corpus())

    results = index.find_experts("Snowflake retail forecasting", (1.0, 0.0, 0.0), limit=5)

    assert results[0].name == "Jane Expert"
    assert results[0].project_ids == ("project-1", "project-2")
    assert results[0].evidence
    assert any(signal.value == "Snowflake" for signal in results[0].matched_signals)


def test_expert_finder_handles_empty_and_validates_vectors() -> None:
    empty = FaissIntelligenceIndexFactory().build(())
    assert empty.find_experts("Snowflake", (), limit=2) == ()

    index = FaissIntelligenceIndexFactory().build(corpus())
    with pytest.raises(ValueError, match="dimensions"):
        index.find_experts("query", (1.0,), limit=2)
    with pytest.raises(ValueError, match="zero"):
        index.find_experts("query", (0.0, 0.0, 0.0), limit=2)
    with pytest.raises(ValueError, match="limit"):
        index.find_experts("query", (1.0, 0.0, 0.0), limit=0)


def test_index_validates_corpus_and_threshold_configuration() -> None:
    factory = FaissIntelligenceIndexFactory()
    with pytest.raises(ValueError, match="unique"):
        factory.build((record(), record()))
    with pytest.raises(ValueError, match="identical dimensions"):
        factory.build((record(), record("p2", embedding=(1.0, 0.0))))
    with pytest.raises(ValueError, match="zero vectors"):
        factory.build((record(embedding=(0.0, 0.0, 0.0)),))
    with pytest.raises(ValueError, match="minimum_similarity"):
        FaissIntelligenceIndexFactory(minimum_similarity=2)
    with pytest.raises(ValueError, match="minimum_expert_score"):
        FaissIntelligenceIndexFactory(minimum_expert_score=-1)
