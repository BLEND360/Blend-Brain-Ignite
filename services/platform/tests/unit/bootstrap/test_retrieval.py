"""Phase 4 composition tests."""

from unittest.mock import sentinel
from uuid import uuid4

import pytest

from blend_brain.bootstrap.configuration import AppEnvironment, Settings
from blend_brain.bootstrap.retrieval import create_question_answering_service


def configured_settings() -> Settings:
    """Return complete offline composition settings."""
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


def test_phase_4_composition_requires_external_configuration() -> None:
    without_openai = configured_settings().model_copy(update={"openai_api_key": None})
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_question_answering_service(without_openai)
    with pytest.raises(ValueError, match="SNOWFLAKE_ENABLED"):
        create_question_answering_service(
            Settings(_env_file=None, app_env=AppEnvironment.TEST, openai_api_key="key")
        )


def test_phase_4_composition_builds_configured_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("blend_brain.bootstrap.retrieval.OpenAI", lambda **_kwargs: sentinel.client)
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.SnowflakeConnectionFactory",
        lambda *_args: sentinel.connection,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.SnowflakeRetrievalCorpusRepository",
        lambda *_args, **_kwargs: sentinel.repository,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.OpenAIQueryEmbeddingGateway",
        lambda *_args, **_kwargs: sentinel.embeddings,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.FaissHybridSearchIndexFactory",
        lambda **_kwargs: sentinel.index_factory,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.HybridRetrievalService",
        lambda **_kwargs: sentinel.retriever,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.OpenAIAnswerGenerator",
        lambda *_args, **_kwargs: sentinel.generator,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.retrieval.QuestionAnsweringService",
        lambda **_kwargs: sentinel.service,
    )

    assert create_question_answering_service(configured_settings()) is sentinel.service
