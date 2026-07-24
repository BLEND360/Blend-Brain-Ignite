"""Authenticated HTTP adapters for grounded business artifacts."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from blend_brain.business_artifacts.application import (
    GenerateOnePagerCommand,
    GenerateProposalCommand,
)
from blend_brain.business_artifacts.domain import (
    ArtifactActor,
    ArtifactAuthorizationError,
    ArtifactKind,
    ArtifactNotFoundError,
    ArtifactPermission,
    ArtifactRequestError,
    ArtifactScope,
    BusinessArtifact,
    BusinessArtifactError,
)
from blend_brain.entrypoints.api.auth import ApiPrincipal, require_principal
from blend_brain.entrypoints.api.schemas import (
    ArtifactCitationResponse,
    ArtifactSectionResponse,
    ArtifactStatementResponse,
    BusinessArtifactResponse,
    GenerateOnePagerRequest,
    GenerateProposalRequest,
)

if TYPE_CHECKING:
    from blend_brain.bootstrap.business_artifacts import BusinessArtifactServices
    from blend_brain.entrypoints.api.services import KnowledgeApiServices

router = APIRouter(prefix="/api/v1/artifacts", tags=["business-artifacts"])
Principal = Annotated[ApiPrincipal, Depends(require_principal)]


def _services(request: Request) -> KnowledgeApiServices:
    return cast("KnowledgeApiServices", request.app.state.api_services)


def _artifacts(request: Request) -> BusinessArtifactServices:
    services = _services(request).artifacts
    if services is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Business artifact generation is not configured.",
        )
    return services


def _security(request: Request, principal: ApiPrincipal) -> tuple[ArtifactActor, ArtifactScope]:
    project_ids = _services(request).catalog.resolve_scope(principal.configured_project_ids)
    if not project_ids:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No projects are accessible.")
    actor = ArtifactActor(
        principal.subject,
        frozenset((ArtifactPermission.GENERATE, ArtifactPermission.EXPORT)),
    )
    return actor, ArtifactScope(project_ids)


@router.post("/proposals", response_model=BusinessArtifactResponse)
def generate_proposal(
    body: GenerateProposalRequest, request: Request, principal: Principal
) -> BusinessArtifactResponse:
    actor, scope = _security(request, principal)
    try:
        artifact = _artifacts(request).proposals.generate(
            GenerateProposalCommand(
                request_id=body.request_id,
                project_ids=tuple(body.project_ids),
                client_name=body.client_name,
                audience=body.audience,
                opportunity=body.opportunity,
                objectives=tuple(body.objectives),
                constraints=tuple(body.constraints),
            ),
            actor=actor,
            scope=scope,
        )
    except BusinessArtifactError as exception:
        raise _http_error(exception) from exception
    return _response(artifact, ArtifactKind.PROPOSAL)


@router.post("/one-pagers", response_model=BusinessArtifactResponse)
def generate_one_pager(
    body: GenerateOnePagerRequest, request: Request, principal: Principal
) -> BusinessArtifactResponse:
    actor, scope = _security(request, principal)
    try:
        artifact = _artifacts(request).one_pagers.generate(
            GenerateOnePagerCommand(
                request_id=body.request_id,
                project_id=body.project_id,
                audience=body.audience,
            ),
            actor=actor,
            scope=scope,
        )
    except BusinessArtifactError as exception:
        raise _http_error(exception) from exception
    return _response(artifact, ArtifactKind.PROJECT_ONE_PAGER)


@router.post("/{kind}/{artifact_id}/pdf", response_class=FileResponse)
def export_pdf(
    kind: ArtifactKind, artifact_id: str, request: Request, principal: Principal
) -> FileResponse:
    actor, scope = _security(request, principal)
    try:
        exported = _artifacts(request).pdf_exports.export(
            artifact_id, kind, actor=actor, scope=scope
        )
    except BusinessArtifactError as exception:
        raise _http_error(exception) from exception
    path = Path(exported.storage_location).joinpath(*PurePosixPath(exported.object_key).parts)
    return FileResponse(
        path,
        media_type=exported.content_type,
        filename=f"{kind.value}-{artifact_id}.pdf",
    )


def _response(artifact: BusinessArtifact, kind: ArtifactKind) -> BusinessArtifactResponse:
    return BusinessArtifactResponse(
        artifact_id=artifact.artifact_id,
        kind=kind.value,
        source_project_ids=list(artifact.source_project_ids),
        title=artifact.title,
        subtitle=artifact.subtitle,
        sections=[
            ArtifactSectionResponse(
                key=section.key,
                heading=section.heading,
                statements=[
                    ArtifactStatementResponse(
                        text=statement.text,
                        citations=[
                            ArtifactCitationResponse(
                                source_id=citation.source_id,
                                quote=citation.quote,
                                source_kind=(
                                    citation.source_kind.value if citation.source_kind else None
                                ),
                                project_id=citation.project_id,
                                document_id=citation.document_id,
                                section_sequence=citation.section_sequence,
                                filename=citation.filename,
                            )
                            for citation in statement.citations
                        ],
                    )
                    for statement in section.statements
                ],
            )
            for section in artifact.sections
        ],
        status=artifact.status.value,
        model=artifact.model,
        prompt_version=artifact.prompt_version,
        created_at=artifact.created_at,
    )


def _http_error(exception: BusinessArtifactError) -> HTTPException:
    if isinstance(exception, ArtifactAuthorizationError):
        status = HTTPStatus.FORBIDDEN
    elif isinstance(exception, ArtifactNotFoundError):
        status = HTTPStatus.NOT_FOUND
    elif isinstance(exception, ArtifactRequestError):
        status = HTTPStatus.UNPROCESSABLE_ENTITY
    else:
        status = HTTPStatus.BAD_GATEWAY
    return HTTPException(status_code=status, detail=str(exception))
