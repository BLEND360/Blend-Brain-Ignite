"""Public error-contract tests."""

from http import HTTPStatus

from fastapi.testclient import TestClient


def test_unknown_route_uses_problem_details(client: TestClient) -> None:
    response = client.get("/does-not-exist", headers={"X-Request-ID": "request-123"})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-request-id"] == "request-123"
    assert response.json() == {
        "type": "https://blendbrain.internal/problems/http-404",
        "title": "Not Found",
        "status": 404,
        "detail": "Not Found",
        "instance": "/does-not-exist",
        "code": "http_404",
        "requestId": "request-123",
    }


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "invalid request id"})

    assert response.status_code == HTTPStatus.OK
    assert response.headers["x-request-id"] != "invalid request id"
    assert len(response.headers["x-request-id"]) == 36
