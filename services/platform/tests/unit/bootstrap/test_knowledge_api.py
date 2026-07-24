"""Authenticated knowledge API composition tests."""

from types import SimpleNamespace
from typing import Any

import pytest

from blend_brain.bootstrap.configuration import AppEnvironment, Settings
from blend_brain.bootstrap.knowledge_api import create_knowledge_api_services


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        api_auth_enabled=True,
        api_static_bearer_token="local-token",  # noqa: S106 - isolated test credential
        snowflake_enabled=True,
        snowflake_account="account",
        snowflake_user="user",
        snowflake_password="password",  # noqa: S106 - isolated test credential
        snowflake_warehouse="warehouse",
        snowflake_database="database",
        openai_api_key="openai-test-key",
    )


def test_composes_shared_scoped_retrieval_and_intelligence(monkeypatch: pytest.MonkeyPatch) -> None:
    from blend_brain.bootstrap import knowledge_api

    retriever = object()
    answering = object()
    catalog: Any = SimpleNamespace(resolve_scope=lambda _ids: ("project-1",))
    intelligence = SimpleNamespace(
        project_similarity=object(),
        expert_finder=object(),
        index_registry=object(),
        knowledge_graph=object(),
    )
    monkeypatch.setattr(knowledge_api, "SnowflakeConnectionFactory", lambda _config: object())
    monkeypatch.setattr(
        knowledge_api, "SnowflakeKnowledgeCatalogRepository", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(knowledge_api, "KnowledgeCatalogService", lambda _repository: catalog)
    monkeypatch.setattr(
        knowledge_api, "create_organizational_intelligence_services", lambda _settings: intelligence
    )
    monkeypatch.setattr(
        knowledge_api, "create_hybrid_retrieval_service", lambda _settings: retriever
    )
    monkeypatch.setattr(
        knowledge_api,
        "create_question_answering_service",
        lambda _settings, supplied: answering if supplied is retriever else None,
    )

    services = create_knowledge_api_services(configured_settings())

    assert services.catalog is catalog
    assert services.retrieval_indexes is retriever
    assert services.question_answering is answering
    assert services.intelligence_indexes is intelligence.index_registry
    assert services.authenticator.authenticate("Bearer local-token").subject == "local-developer"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"api_auth_enabled": False, "api_static_bearer_token": None},
            "require local bearer",
        ),
        ({"snowflake_database": None}, "Snowflake settings are incomplete"),
    ],
)
def test_rejects_incomplete_runtime_configuration(overrides: dict[str, Any], message: str) -> None:
    settings = configured_settings().model_copy(update=overrides)

    with pytest.raises(ValueError, match=message):
        create_knowledge_api_services(settings)
