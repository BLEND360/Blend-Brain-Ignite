"""Phase 8 composition tests."""

from unittest.mock import sentinel
from uuid import uuid4

import pytest

from blend_brain.bootstrap.business_artifacts import create_business_artifact_services
from blend_brain.bootstrap.configuration import AppEnvironment, Settings


def configured_settings() -> Settings:
    """Return complete offline Phase 8 configuration."""
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
        artifact_export_directory=".local/test-artifacts",
    )


def test_phase_8_requires_openai_and_snowflake() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_business_artifact_services(
            configured_settings().model_copy(update={"openai_api_key": None})
        )
    with pytest.raises(ValueError, match="SNOWFLAKE_ENABLED"):
        create_business_artifact_services(
            Settings(_env_file=None, app_env=AppEnvironment.TEST, openai_api_key="key")
        )


def test_phase_8_composes_generation_and_export_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.SnowflakeConnectionFactory",
        lambda *_args: sentinel.connection,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.SnowflakeBusinessArtifactRepository",
        lambda *_args, **_kwargs: sentinel.repository,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.OpenAI", lambda **_kwargs: sentinel.openai
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.OpenAIBusinessArtifactGenerator",
        lambda *_args, **_kwargs: sentinel.generator,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.LocalArtifactObjectStore",
        lambda *_args, **_kwargs: sentinel.object_store,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.business_artifacts.ReportLabPdfRenderer",
        lambda: sentinel.renderer,
    )

    services = create_business_artifact_services(configured_settings())

    assert services.proposals is not None
    assert services.one_pagers is not None
    assert services.pdf_exports is not None
