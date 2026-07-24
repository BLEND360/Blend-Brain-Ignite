"""Phase 7 composition tests."""

from unittest.mock import sentinel
from uuid import uuid4

import pytest

from blend_brain.bootstrap.configuration import AppEnvironment, Settings
from blend_brain.bootstrap.knowledge_lifecycle import create_knowledge_lifecycle_services


def configured_settings() -> Settings:
    """Return complete offline Snowflake settings."""
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        snowflake_enabled=True,
        snowflake_account="account",
        snowflake_user="user",
        snowflake_warehouse="warehouse",
        snowflake_database="database",
        snowflake_password=uuid4().hex,
    )


def test_phase_7_requires_snowflake() -> None:
    with pytest.raises(ValueError, match="SNOWFLAKE_ENABLED"):
        create_knowledge_lifecycle_services(Settings(_env_file=None, app_env=AppEnvironment.TEST))


def test_phase_7_composes_all_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "blend_brain.bootstrap.knowledge_lifecycle.SnowflakeConnectionFactory",
        lambda *_args: sentinel.connection,
    )
    monkeypatch.setattr(
        "blend_brain.bootstrap.knowledge_lifecycle.SnowflakeKnowledgeLifecycleRepository",
        lambda *_args, **_kwargs: sentinel.repository,
    )

    services = create_knowledge_lifecycle_services(configured_settings())

    assert services.gap_detection is not None
    assert services.capture is not None
    assert services.approval is not None
