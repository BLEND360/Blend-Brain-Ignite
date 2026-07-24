"""Operational API endpoint tests."""

from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from fastapi import FastAPI


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_readiness(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "ok"


def test_not_ready_returns_service_unavailable(client: TestClient) -> None:
    app = cast("FastAPI", client.app)
    app.state.ready = False

    response = client.get("/health/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["status"] == "not_ready"
