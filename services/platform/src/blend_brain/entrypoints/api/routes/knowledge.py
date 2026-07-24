"""Authenticated HTTP adapters for knowledge and intelligence workflows."""

from __future__ import annotations

from hashlib import sha256
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from blend_brain.entrypoints.api.auth import ApiPrincipal, require_principal
from blend_brain.entrypoints.api.schemas import (
    AnswerClaimResponse,
    AnswerResponse,
    CitationResponse,
    ConfidenceBreakdownResponse,
    ConfidenceResponse,
    DashboardResponse,
    DocumentResponse,
    EvidenceResponse,
    ExpertEvidenceResponse,
    ExpertMatchResponse,
    ExpertResponse,
    ExpertSearchRequest,
    ExpertSearchResponse,
    GroundedClaimResponse,
    IndustryCountResponse,
    ProjectCatalogResponse,
    ProjectDetailsResponse,
    ProjectDnaResponse,
    ProjectSummaryResponse,
    QuestionRequest,
    SearchResponse,
    SimilaritySignalResponse,
    SimilarProjectResponse,
    SimilarProjectsResponse,
)
from blend_brain.knowledge_retrieval.domain import InvalidRetrievalRequestError, RetrievalScope
from blend_brain.organizational_intelligence.domain import (
    IntelligenceRequestError,
    IntelligenceScope,
    ProjectNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["knowledge"])
Principal = Annotated[ApiPrincipal, Depends(require_principal)]

if TYPE_CHECKING:
    from blend_brain.entrypoints.api.services import KnowledgeApiServices
    from blend_brain.knowledge_catalog.domain import CatalogProject
    from blend_brain.knowledge_enrichment.domain import GroundedClaim


def _services(request: Request) -> KnowledgeApiServices:
    return cast("KnowledgeApiServices", request.app.state.api_services)


def _project_ids(request: Request, principal: ApiPrincipal) -> tuple[str, ...]:
    project_ids = _services(request).catalog.resolve_scope(principal.configured_project_ids)
    if not project_ids:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="No projects are accessible.")
    return project_ids


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(request: Request, principal: Principal) -> DashboardResponse:
    snapshot = _services(request).catalog.dashboard(_project_ids(request, principal))
    return DashboardResponse(
        total_projects=snapshot.total_projects,
        indexed_documents=snapshot.indexed_documents,
        identified_experts=snapshot.identified_experts,
        knowledge_coverage=snapshot.knowledge_coverage,
        recent_projects=[_summary(project) for project in snapshot.recent_projects],
        top_industries=[
            IndustryCountResponse(name=item.name, project_count=item.project_count)
            for item in snapshot.top_industries
        ],
        updated_at=snapshot.updated_at,
    )


@router.get("/projects", response_model=ProjectCatalogResponse)
def project_catalog(
    request: Request,
    principal: Principal,
    query: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 1_000,
) -> ProjectCatalogResponse:
    project_ids = _project_ids(request, principal)
    projects = _services(request).catalog.projects(project_ids, project_ids)
    normalized = query.strip().casefold() if query else ""
    if normalized:
        projects = tuple(
            project
            for project in projects
            if normalized
            in " ".join(
                value
                for value in (
                    project.display_name,
                    project.dna.project_name.value
                    if project.dna and project.dna.project_name
                    else None,
                    project.dna.client_name.value
                    if project.dna and project.dna.client_name
                    else None,
                    project.dna.industry.value if project.dna and project.dna.industry else None,
                )
                if value
            ).casefold()
        )
    ordered = tuple(sorted(projects, key=lambda project: _summary(project).name.casefold()))
    return ProjectCatalogResponse(
        projects=[_summary(project) for project in ordered[:limit]],
        total=len(ordered),
    )


@router.post("/questions", response_model=SearchResponse)
def questions(body: QuestionRequest, request: Request, principal: Principal) -> SearchResponse:
    project_ids = _project_ids(request, principal)
    try:
        answer = _services(request).question_answering.ask(
            body.question, RetrievalScope(project_ids)
        )
    except InvalidRetrievalRequestError as exception:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(exception)
        ) from exception
    related_ids = tuple(dict.fromkeys(citation.project_id for citation in answer.citations))
    related = _services(request).catalog.projects(related_ids, project_ids)
    return SearchResponse(
        answer=AnswerResponse(
            question=answer.question,
            answerable=answer.answerable,
            answer=answer.answer,
            claims=[
                AnswerClaimResponse(text=claim.text, citation_ids=list(claim.citation_ids))
                for claim in answer.claims
            ],
            citations=[
                CitationResponse(
                    citation_id=item.citation_id,
                    project_id=item.project_id,
                    document_id=item.document_id,
                    filename=item.filename,
                    section_sequence=item.section_sequence,
                    quote=item.quote,
                    page_number=item.page_number,
                    slide_number=item.slide_number,
                    heading=item.heading,
                )
                for item in answer.citations
            ],
            confidence=ConfidenceResponse(
                score=answer.confidence.score,
                band=answer.confidence.band.value,
                breakdown=ConfidenceBreakdownResponse(
                    retrieval_strength=answer.confidence.breakdown.retrieval_strength,
                    citation_coverage=answer.confidence.breakdown.citation_coverage,
                    source_diversity=answer.confidence.breakdown.source_diversity,
                ),
            ),
            reason=answer.reason,
        ),
        related_projects=[_summary(project) for project in related],
    )


@router.get("/projects/{project_id}", response_model=ProjectDetailsResponse)
def project_details(
    project_id: str, request: Request, principal: Principal
) -> ProjectDetailsResponse:
    project = _services(request).catalog.project(project_id, _project_ids(request, principal))
    if project is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Project was not found.")
    summary = _summary(project)
    dna = project.dna
    return ProjectDetailsResponse(
        **summary.model_dump(),
        challenge=(dna.business_challenges[0].value if dna and dna.business_challenges else None),
        solution=(
            "; ".join(claim.value for claim in dna.capabilities)
            if dna and dna.capabilities
            else None
        ),
        outcomes=[claim.value for claim in dna.outcomes] if dna else [],
        capabilities=[claim.value for claim in dna.capabilities] if dna else [],
        experts=[
            ExpertResponse(id=_expert_id(claim.value), name=claim.value, role=None)
            for claim in (dna.experts if dna else ())
        ],
        documents=[
            DocumentResponse(
                id=document.document_id,
                filename=document.filename,
                format=document.document_format,
                section_count=document.section_count,
                updated_at=document.updated_at,
            )
            for document in project.documents
        ],
        dna=_dna(project) if dna else None,
    )


@router.get("/projects/{project_id}/dna", response_model=ProjectDnaResponse)
def project_dna(project_id: str, request: Request, principal: Principal) -> ProjectDnaResponse:
    project = _services(request).catalog.project(project_id, _project_ids(request, principal))
    if project is None or project.dna is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Project DNA was not found.")
    return _dna(project)


@router.get("/projects/{project_id}/similar", response_model=SimilarProjectsResponse)
def similar_projects(
    project_id: str,
    request: Request,
    principal: Principal,
    limit: Annotated[int, Query(ge=1, le=50)] = 6,
) -> SimilarProjectsResponse:
    scope = IntelligenceScope(_project_ids(request, principal))
    try:
        matches = _services(request).project_similarity.find_similar(project_id, scope, limit=limit)
    except ProjectNotFoundError as exception:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exception)) from exception
    except IntelligenceRequestError as exception:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(exception)
        ) from exception
    return SimilarProjectsResponse(
        projects=[
            SimilarProjectResponse(
                project_id=item.project_id,
                display_name=item.display_name,
                score=item.score,
                shared_signals=[
                    SimilaritySignalResponse(kind=signal.kind.value, value=signal.value)
                    for signal in item.shared_signals
                ],
            )
            for item in matches
        ]
    )


@router.post("/experts/search", response_model=ExpertSearchResponse)
def expert_search(
    body: ExpertSearchRequest, request: Request, principal: Principal
) -> ExpertSearchResponse:
    try:
        matches = _services(request).expert_finder.find(
            body.query, IntelligenceScope(_project_ids(request, principal))
        )
    except IntelligenceRequestError as exception:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(exception)
        ) from exception
    return ExpertSearchResponse(
        experts=[
            ExpertMatchResponse(
                expert_id=item.expert_id,
                name=item.name,
                score=item.score,
                project_ids=list(item.project_ids),
                matched_signals=[
                    SimilaritySignalResponse(kind=signal.kind.value, value=signal.value)
                    for signal in item.matched_signals
                ],
                evidence=[
                    ExpertEvidenceResponse(
                        document_id=evidence.document_id,
                        section_sequence=evidence.section_sequence,
                        quote=evidence.quote,
                    )
                    for evidence in item.evidence
                ],
            )
            for item in matches
        ]
    )


def _summary(project: CatalogProject) -> ProjectSummaryResponse:
    dna = project.dna
    return ProjectSummaryResponse(
        id=project.project_id,
        name=(dna.project_name.value if dna and dna.project_name else project.display_name),
        client=dna.client_name.value if dna and dna.client_name else None,
        industry=dna.industry.value if dna and dna.industry else None,
        engagement_type=dna.engagement_type.value if dna and dna.engagement_type else None,
        summary=dna.summary.value if dna and dna.summary else None,
        technologies=[claim.value for claim in dna.technologies] if dna else [],
        document_count=project.document_count,
        updated_at=project.updated_at,
    )


def _dna(project: CatalogProject) -> ProjectDnaResponse:
    dna = project.dna
    if dna is None:  # pragma: no cover - callers guard this invariant
        raise ValueError("Project DNA is required")
    documents = {document.document_id: document.filename for document in project.documents}
    locations = {
        sequence: (page, slide, heading)
        for sequence, page, slide, heading in project.section_locations
    }

    def mapped(claim: GroundedClaim | None) -> GroundedClaimResponse | None:
        if claim is None:
            return None
        return GroundedClaimResponse(
            value=claim.value,
            confidence=claim.confidence.value,
            evidence=[
                EvidenceResponse(
                    document_id=dna.document_id,
                    filename=documents.get(dna.document_id, "Unknown source"),
                    section_sequence=evidence.section_sequence,
                    quote=evidence.quote,
                    page_number=locations.get(evidence.section_sequence, (None, None, None))[0],
                    slide_number=locations.get(evidence.section_sequence, (None, None, None))[1],
                    heading=locations.get(evidence.section_sequence, (None, None, None))[2],
                )
                for evidence in claim.evidence
            ],
        )

    def collection(claims: tuple[GroundedClaim, ...]) -> list[GroundedClaimResponse]:
        return [item for claim in claims if (item := mapped(claim)) is not None]

    return ProjectDnaResponse(
        id=dna.dna_id,
        project_id=dna.project_id,
        version=dna.version,
        generated_at=dna.generated_at,
        model=dna.model,
        project_name=mapped(dna.project_name),
        client_name=mapped(dna.client_name),
        industry=mapped(dna.industry),
        engagement_type=mapped(dna.engagement_type),
        summary=mapped(dna.summary),
        business_challenges=collection(dna.business_challenges),
        use_cases=collection(dna.use_cases),
        capabilities=collection(dna.capabilities),
        technologies=collection(dna.technologies),
        data_sources=collection(dna.data_sources),
        cloud_platforms=collection(dna.cloud_platforms),
        outcomes=collection(dna.outcomes),
        differentiators=collection(dna.differentiators),
        experts=collection(dna.experts),
    )


def _expert_id(name: str) -> str:
    return sha256(name.strip().casefold().encode()).hexdigest()[:24]
