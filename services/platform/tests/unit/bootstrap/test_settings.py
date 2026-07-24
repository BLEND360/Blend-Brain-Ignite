"""Configuration safety tests."""

from typing import Any

import pytest
from pydantic import ValidationError

from blend_brain.bootstrap.configuration import (
    AppEnvironment,
    LogFormat,
    Settings,
    get_settings,
)


def test_normalizes_api_prefix_and_log_level() -> None:
    settings = Settings(_env_file=None, api_base_path="/api/v1/", log_level="warning")

    assert settings.api_base_path == "/api/v1"
    assert settings.log_level == "WARNING"


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"api_base_path": "/"}, "API_BASE_PATH must be an absolute, non-root path"),
        ({"log_level": "verbose"}, "LOG_LEVEL must be one of"),
        ({"request_id_header": "invalid header"}, "REQUEST_ID_HEADER must be"),
        (
            {"app_env": AppEnvironment.PRODUCTION, "trusted_hosts": ["*"]},
            "Wildcard trusted hosts are prohibited in production",
        ),
    ],
)
def test_rejects_invalid_field_values(
    overrides: dict[str, Any],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        Settings(_env_file=None, **overrides)


def test_get_settings_is_process_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLEND_BRAIN_APP_ENV", "test")
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"app_env": AppEnvironment.PRODUCTION, "debug": True},
            "DEBUG cannot be enabled in production",
        ),
        (
            {"app_env": AppEnvironment.PRODUCTION, "log_format": LogFormat.CONSOLE},
            "LOG_FORMAT must be json in production",
        ),
        (
            {"cors_allowed_origins": ["*"], "cors_allow_credentials": True},
            "Wildcard CORS origins cannot be used with credentials",
        ),
        (
            {"otel_enabled": True, "otel_exporter_otlp_endpoint": None},
            "OTEL_EXPORTER_OTLP_ENDPOINT is required",
        ),
        (
            {"snowflake_enabled": True},
            "Snowflake configuration is missing",
        ),
        (
            {
                "snowflake_enabled": True,
                "snowflake_account": "account",
                "snowflake_user": "user",
                "snowflake_warehouse": "warehouse",
                "snowflake_database": "database",
            },
            "Snowflake requires password or private-key authentication",
        ),
        (
            {"retrieval_dense_weight": 0, "retrieval_lexical_weight": 0},
            "At least one retrieval weight",
        ),
    ],
)
def test_rejects_unsafe_configuration(
    overrides: dict[str, Any],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        Settings(_env_file=None, **overrides)
