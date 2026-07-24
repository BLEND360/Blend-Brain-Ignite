"""Consistent problem-detail responses for HTTP failures."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import structlog
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

from blend_brain.shared.application.request_context import get_request_id

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

logger = structlog.get_logger(__name__)


class ValidationIssue(BaseModel):
    """A safe description of one invalid request field."""

    model_config = ConfigDict(populate_by_name=True)

    location: list[str | int]
    message: str
    error_type: str = Field(alias="errorType")


class ProblemDetail(BaseModel):
    """Stable API error contract based on HTTP problem details."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str = Field(alias="requestId")
    errors: list[ValidationIssue] | None = None


def _title_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _problem_response(problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(by_alias=True, exclude_none=True),
        media_type="application/problem+json",
        headers={"Cache-Control": "no-store"},
    )


async def http_exception_handler(request: Request, exception: HTTPException) -> JSONResponse:
    """Translate framework HTTP failures into the public error contract."""
    problem = ProblemDetail(
        type=f"https://blendbrain.internal/problems/http-{exception.status_code}",
        title=_title_for_status(exception.status_code),
        status=exception.status_code,
        detail=exception.detail,
        instance=request.url.path,
        code=f"http_{exception.status_code}",
        request_id=get_request_id(),
    )
    return _problem_response(problem)


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Return field errors without echoing rejected user input."""
    issues = [
        ValidationIssue(
            location=[str(part) if not isinstance(part, int) else part for part in error["loc"]],
            message=error["msg"],
            error_type=error["type"],
        )
        for error in exception.errors()
    ]
    problem = ProblemDetail(
        type="https://blendbrain.internal/problems/request-validation",
        title="Request validation failed",
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail="One or more request fields are invalid.",
        instance=request.url.path,
        code="request_validation_failed",
        request_id=get_request_id(),
        errors=issues,
    )
    return _problem_response(problem)


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    """Log unexpected errors and return a non-sensitive response."""
    logger.exception(
        "request.unhandled_exception",
        path=request.url.path,
        exception_type=type(exception).__name__,
    )
    problem = ProblemDetail(
        type="https://blendbrain.internal/problems/internal-server-error",
        title="Internal Server Error",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        detail="The request could not be completed.",
        instance=request.url.path,
        code="internal_server_error",
        request_id=get_request_id(),
    )
    return _problem_response(problem)


def install_exception_handlers(app: FastAPI) -> None:
    """Register public exception handlers on the API application."""
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)


def problem_openapi_examples() -> dict[str, Any]:
    """Return shared OpenAPI error examples for future route documentation."""
    return {
        "application/problem+json": {
            "example": {
                "type": "https://blendbrain.internal/problems/request-validation",
                "title": "Request validation failed",
                "status": 422,
                "detail": "One or more request fields are invalid.",
                "instance": "/api/v1/example",
                "code": "request_validation_failed",
                "requestId": "01JEXAMPLE",
            }
        }
    }
