"""Phase 3 composition tests."""

from unittest.mock import sentinel
from uuid import uuid4

import pytest

from blend_brain.bootstrap.configuration import AppEnvironment, Settings
from blend_brain.bootstrap.enrichment import create_knowledge_enrichment_service


def test_composition_requires_openai_and_enabled_snowflake() -> None:
    without_openai = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        snowflake_enabled=True,
        snowflake_account="account",
        snowflake_user="user",
        snowflake_warehouse="warehouse",
        snowflake_database="database",
        snowflake_password=uuid4().hex,
    )
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_knowledge_enrichment_service(without_openai)

    with pytest.raises(ValueError, match="SNOWFLAKE_ENABLED"):
        create_knowledge_enrichment_service(
            Settings(_env_file=None, app_env=AppEnvironment.TEST, openai_api_key="test-key")
        )


def test_composition_builds_configured_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
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
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.OpenAI", lambda **_kwargs: sentinel.client
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.OpenAIProjectDNAGenerator",
        lambda *_args, **_kwargs: sentinel.dna,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.OpenAIEmbeddingGateway",
        lambda *_args, **_kwargs: sentinel.embeddings,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.SnowflakeConnectionFactory",
        lambda *_args: sentinel.connection_factory,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.SnowflakeKnowledgeRepository",
        lambda *_args, **_kwargs: sentinel.repository,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.enrichment.KnowledgeEnrichmentService",
        lambda **_kwargs: sentinel.service,
    )

    assert create_knowledge_enrichment_service(settings) is sentinel.service
