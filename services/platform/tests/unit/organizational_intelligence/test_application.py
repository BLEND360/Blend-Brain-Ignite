"""Phase 6 application workflow tests."""

import pytest

from blend_brain.organizational_intelligence.application import (
    ExpertFinderService,
    IntelligenceIndexRegistry,
    ProjectSimilarityService,
)
from blend_brain.organizational_intelligence.domain import (
    IntelligenceRequestError,
    IntelligenceScope,
    ProjectIntelligenceRecord,
)
from blend_brain.organizational_intelligence.infrastructure import FaissIntelligenceIndexFactory
from tests.unit.organizational_intelligence.helpers import record


class Repository:
    """Scoped corpus repository test double."""

    def __init__(self) -> None:
        self.calls = 0

    def load(self, scope: IntelligenceScope) -> tuple[ProjectIntelligenceRecord, ...]:
        self.calls += 1
        return tuple(
            record(project_id, expert_name="Jane Expert") for project_id in scope.project_ids
        )


class Embeddings:
    """Deterministic expertise query embedding gateway."""

    def __init__(self) -> None:
        self.query = ""

    def embed_query(self, query: str) -> tuple[float, ...]:
        self.query = query
        return (1.0, 0.0, 0.0)


def test_registry_caches_refreshes_invalidates_and_evicts_scopes() -> None:
    repository = Repository()
    registry = IntelligenceIndexRegistry(
        repository, FaissIntelligenceIndexFactory(), max_cached_scopes=1
    )
    first = IntelligenceScope(("p1", "p2"))
    second = IntelligenceScope(("p3",))

    assert registry.get(first) is registry.get(first)
    assert repository.calls == 1
    registry.get(second)
    registry.get(first)
    assert repository.calls == 3
    assert registry.refresh(first) == 2
    assert registry.invalidate(first) is True
    assert registry.invalidate(first) is False


def test_similarity_and_expert_services_orchestrate_authorized_index() -> None:
    registry = IntelligenceIndexRegistry(
        Repository(),
        FaissIntelligenceIndexFactory(minimum_similarity=0, minimum_expert_score=0),
    )
    scope = IntelligenceScope(("p1", "p2"))
    similarity = ProjectSimilarityService(registry)
    embeddings = Embeddings()
    experts = ExpertFinderService(registry, embeddings)

    assert similarity.find_similar("p1", scope)[0].project_id == "p2"
    assert experts.find("Snowflake expert", scope)[0].name == "Jane Expert"
    assert embeddings.query == "Snowflake expert"


@pytest.mark.parametrize("project_id", ["", "   "])
def test_similarity_rejects_invalid_requests(project_id: str) -> None:
    registry = IntelligenceIndexRegistry(Repository(), FaissIntelligenceIndexFactory())
    service = ProjectSimilarityService(registry)
    with pytest.raises(IntelligenceRequestError):
        service.find_similar(project_id, IntelligenceScope(("p",)))
    with pytest.raises(IntelligenceRequestError, match="limit"):
        service.find_similar("p", IntelligenceScope(("p",)), limit=0)


def test_expert_finder_rejects_empty_oversized_and_invalid_limits() -> None:
    registry = IntelligenceIndexRegistry(Repository(), FaissIntelligenceIndexFactory())
    service = ExpertFinderService(registry, Embeddings(), max_query_characters=4)
    scope = IntelligenceScope(("p",))

    with pytest.raises(IntelligenceRequestError, match="empty"):
        service.find(" ", scope)
    with pytest.raises(IntelligenceRequestError, match="character limit"):
        service.find("long query", scope)
    with pytest.raises(IntelligenceRequestError, match="limit"):
        service.find("test", scope, limit=0)


def test_scope_and_service_configuration_invariants() -> None:
    assert IntelligenceScope((" b ", "a", "a")).project_ids == ("a", "b")
    assert IntelligenceScope(("a",)).fingerprint == IntelligenceScope(("a",)).fingerprint
    with pytest.raises(ValueError, match="at least one"):
        IntelligenceScope(())
    with pytest.raises(ValueError, match="greater than zero"):
        IntelligenceIndexRegistry(
            Repository(), FaissIntelligenceIndexFactory(), max_cached_scopes=0
        )
    registry = IntelligenceIndexRegistry(Repository(), FaissIntelligenceIndexFactory())
    with pytest.raises(ValueError, match="default_limit"):
        ProjectSimilarityService(registry, default_limit=0)
    with pytest.raises(ValueError, match="limits"):
        ExpertFinderService(registry, Embeddings(), default_limit=0)
