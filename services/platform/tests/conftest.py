"""Shared backend test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from blend_brain.bootstrap.application import create_app
from blend_brain.bootstrap.configuration import AppEnvironment, LogFormat, Settings


@pytest.fixture
def settings() -> Settings:
    """Return isolated test configuration without reading environment files."""
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        log_format=LogFormat.JSON,
        trusted_hosts=["testserver"],
        docs_enabled=False,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Run the application lifespan for an API test client."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client
