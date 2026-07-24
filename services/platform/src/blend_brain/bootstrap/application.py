"""FastAPI application factory and process lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from blend_brain.bootstrap.configuration import Settings, get_settings
from blend_brain.bootstrap.logging import configure_logging
from blend_brain.bootstrap.telemetry import configure_telemetry
from blend_brain.entrypoints.api.errors import install_exception_handlers
from blend_brain.entrypoints.api.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from blend_brain.entrypoints.api.routes.health import router as health_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from blend_brain.entrypoints.api.services import KnowledgeApiServices


def create_app(
    settings: Settings | None = None, api_services: KnowledgeApiServices | None = None
) -> FastAPI:
    """Build a fully configured API application."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        logger.info(
            "application.starting",
            environment=resolved_settings.app_env.value,
            version=resolved_settings.app_version,
        )
        app.state.ready = True
        logger.info("application.ready")
        try:
            yield
        finally:
            app.state.ready = False
            telemetry_provider = getattr(app.state, "telemetry_provider", None)
            if telemetry_provider is not None:
                telemetry_provider.shutdown()
            logger.info("application.stopped")

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    openapi_url = f"{resolved_settings.api_base_path}/openapi.json" if docs_url else None
    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.ready = False

    if api_services is not None:
        app.state.api_services = api_services
    elif resolved_settings.api_auth_enabled:
        from blend_brain.bootstrap.knowledge_api import create_knowledge_api_services

        app.state.api_services = create_knowledge_api_services(resolved_settings)

    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_allowed_origins,
            allow_credentials=resolved_settings.cors_allow_credentials,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Accept", "Authorization", "Content-Type", "Idempotency-Key"],
            expose_headers=[resolved_settings.request_id_header],
        )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_settings.trusted_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=resolved_settings.request_id_header,
    )

    install_exception_handlers(app)
    app.include_router(health_router)
    if hasattr(app.state, "api_services"):
        from blend_brain.entrypoints.api.routes.artifacts import router as artifact_router
        from blend_brain.entrypoints.api.routes.knowledge import router as knowledge_router

        app.include_router(knowledge_router)
        app.include_router(artifact_router)
    app.state.telemetry_provider = configure_telemetry(app, resolved_settings)
    return app
