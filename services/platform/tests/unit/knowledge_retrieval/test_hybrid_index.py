"""Hybrid index and domain invariant tests."""

import pytest

from blend_brain.knowledge_retrieval.domain import IndexedSection, RetrievalScope
from blend_brain.knowledge_retrieval.infrastructure.hybrid_index import (
    FaissHybridSearchIndexFactory,
)
from tests.unit.knowledge_retrieval.helpers import section


def test_scope_is_nonempty_normalized_and_has_stable_fingerprint() -> None:
    scope = RetrievalScope((" project-2 ", "project-1", "project-1"))

    assert scope.project_ids == ("project-1", "project-2")
    assert scope.fingerprint == RetrievalScope(("project-2", "project-1")).fingerprint
    with pytest.raises(ValueError, match="at least one"):
        RetrievalScope(())
    with pytest.raises(ValueError, match="cannot be empty"):
        RetrievalScope((" ",))


def test_hybrid_index_uses_lexical_signal_to_rescue_semantic_miss() -> None:
    sections = (
        section("a", text="Generic cloud platform", embedding=(1.0, 0.0, 0.0)),
        section("b", text="General analytics delivery", embedding=(0.8, 0.2, 0.0)),
        section(
            "c",
            text="The rareterm solution improved planning.",
            embedding=(0.0, 1.0, 0.0),
        ),
    )
    index = FaissHybridSearchIndexFactory().build(sections)

    results = index.search("rareterm", (1.0, 0.0, 0.0), limit=2)

    assert results[0].section.section_id == "c"
    assert results[0].lexical_rank == 1
    assert [result.source_id for result in results] == ["S1", "S2"]


def test_hybrid_index_handles_empty_and_validates_vectors_and_config() -> None:
    factory = FaissHybridSearchIndexFactory(dense_weight=1, lexical_weight=0)
    assert factory.build(()).search("question", (1.0,), limit=1) == ()

    with pytest.raises(ValueError, match="identical dimensions"):
        factory.build((section(), section("other", embedding=(1.0, 0.0))))
    with pytest.raises(ValueError, match="zero vectors"):
        factory.build((section(embedding=(0.0, 0.0, 0.0)),))
    index = factory.build((section(),))
    with pytest.raises(ValueError, match="dimensions"):
        index.search("question", (1.0, 0.0), limit=1)
    with pytest.raises(ValueError, match="zero vector"):
        index.search("question", (0.0, 0.0, 0.0), limit=1)
    with pytest.raises(ValueError, match="limit"):
        index.search("question", (1.0, 0.0, 0.0), limit=0)
    with pytest.raises(ValueError, match="weight"):
        FaissHybridSearchIndexFactory(dense_weight=0, lexical_weight=0)
    with pytest.raises(ValueError, match="greater than zero"):
        FaissHybridSearchIndexFactory(rrf_k=0)


def test_indexed_section_rejects_invalid_domain_state() -> None:
    with pytest.raises(ValueError, match="sequence"):
        IndexedSection("s", "p", "d", "f", 0, "body", "text", (1.0,))
    with pytest.raises(ValueError, match="finite"):
        section(embedding=(float("nan"),))
