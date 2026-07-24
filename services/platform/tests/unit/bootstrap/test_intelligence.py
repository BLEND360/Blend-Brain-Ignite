"""Phase 6 composition tests."""

from unittest.mock import sentinel
from uuid import uuid4

import pytest

from blend_brain.bootstrap.configuration import AppEnvironment, Settings
from blend_brain.bootstrap.intelligence import create_organizational_intelligence_services


def configured_settings() -> Settings:
    """Return complete offline Phase 6 settings."""
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        openai_api_key="test-key",
        snowflake_enabled=True,
        snowflake_account="account",
        snowflake_user="user",
        snowflake_warehouse="warehouse",
        snowflake_database="database",
        snowflake_password=uuid4().hex,
    )


def test_phase_6_composition_requires_external_configuration() -> None:
    without_openai = configured_settings().model_copy(update={"openai_api_key": None})
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_organizational_intelligence_services(without_openai)
    with pytest.raises(ValueError, match="SNOWFLAKE_ENABLED"):
        create_organizational_intelligence_services(
            Settings(_env_file=None, app_env=AppEnvironment.TEST, openai_api_key="key")
        )


def test_phase_6_composition_builds_all_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.SnowflakeConnectionFactory",
        lambda *_args: sentinel.connection,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.SnowflakeKnowledgeGraphRepository",
        lambda *_args, **_kwargs: sentinel.graph_repository,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.SnowflakeIntelligenceRepository",
        lambda *_args, **_kwargs: sentinel.corpus_repository,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.FaissIntelligenceIndexFactory",
        lambda **_kwargs: sentinel.index_factory,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.IntelligenceIndexRegistry",
        lambda *_args, **_kwargs: sentinel.registry,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.OpenAI", lambda **_kwargs: sentinel.client
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.OpenAIIntelligenceEmbeddingGateway",
        lambda *_args, **_kwargs: sentinel.embedding_gateway,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.KnowledgeGraphProjector",
        lambda: sentinel.projector,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.KnowledgeGraphService",
        lambda *_args: sentinel.graph_service,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.ProjectSimilarityService",
        lambda *_args, **_kwargs: sentinel.similarity_service,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.intelligence.ExpertFinderService",
        lambda *_args, **_kwargs: sentinel.expert_service,
    )

    services = create_organizational_intelligence_services(configured_settings())

    assert services.knowledge_graph is sentinel.graph_service
    assert services.project_similarity is sentinel.similarity_service
    assert services.expert_finder is sentinel.expert_service
    assert services.index_registry is sentinel.registry
