"""Authentication adapter and immutable API principal."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, cast

from fastapi import Header, HTTPException, Request

if TYPE_CHECKING:
    from blend_brain.entrypoints.api.services import KnowledgeApiServices


@dataclass(frozen=True, slots=True)
class ApiPrincipal:
    """Identity and server-established project access configuration."""

    subject: str
    configured_project_ids: tuple[str, ...]


class StaticBearerAuthenticator:
    """Constant-time local bearer validation behind a replaceable boundary."""

    def __init__(
        self,
        *,
        enabled: bool,
        token: str | None,
        subject: str,
        project_ids: tuple[str, ...],
    ) -> None:
        self._enabled = enabled
        self._token = token
        self._principal = ApiPrincipal(subject.strip(), project_ids)

    def authenticate(self, authorization: str | None) -> ApiPrincipal:
        """Validate one RFC 6750 bearer credential without logging it."""
        if not self._enabled or self._token is None:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail="Authenticated knowledge APIs are not configured.",
            )
        scheme, separator, credential = (authorization or "").partition(" ")
        if (
            separator != " "
            or scheme.casefold() != "bearer"
            or not hmac.compare_digest(credential, self._token)
        ):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="A valid bearer credential is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return self._principal


def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
) -> ApiPrincipal:
    """Resolve the configured authenticator without a bootstrap dependency."""
    services = cast("KnowledgeApiServices", request.app.state.api_services)
    return services.authenticator.authenticate(authorization)
