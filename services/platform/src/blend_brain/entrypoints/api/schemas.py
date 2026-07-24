"""Versioned public schemas for knowledge APIs."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=_camel, populate_by_name=True)


class ProjectSummaryResponse(ApiModel):
    id: str
    name: str
    client: str | None
    industry: str | None
    engagement_type: str | None
    summary: str | None
    technologies: list[str]
    document_count: int
    updated_at: AwareDatetime


class IndustryCountResponse(ApiModel):
    name: str
    project_count: int


class DashboardResponse(ApiModel):
    total_projects: int
    indexed_documents: int
    identified_experts: int
    knowledge_coverage: float
    recent_projects: list[ProjectSummaryResponse]
    top_industries: list[IndustryCountResponse]
    updated_at: AwareDatetime


class ProjectCatalogResponse(ApiModel):
    projects: list[ProjectSummaryResponse]
    total: int


class EvidenceResponse(ApiModel):
    document_id: str
    filename: str
    section_sequence: int
    quote: str
    page_number: int | None
    slide_number: int | None
    heading: str | None


class GroundedClaimResponse(ApiModel):
    value: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[EvidenceResponse]


class ProjectDnaResponse(ApiModel):
    id: str
    project_id: str
    version: int
    generated_at: AwareDatetime
    model: str
    project_name: GroundedClaimResponse | None
    client_name: GroundedClaimResponse | None
    industry: GroundedClaimResponse | None
    engagement_type: GroundedClaimResponse | None
    summary: GroundedClaimResponse | None
    business_challenges: list[GroundedClaimResponse]
    use_cases: list[GroundedClaimResponse]
    capabilities: list[GroundedClaimResponse]
    technologies: list[GroundedClaimResponse]
    data_sources: list[GroundedClaimResponse]
    cloud_platforms: list[GroundedClaimResponse]
    outcomes: list[GroundedClaimResponse]
    differentiators: list[GroundedClaimResponse]
    experts: list[GroundedClaimResponse]


class DocumentResponse(ApiModel):
    id: str
    filename: str
    format: Literal["pptx", "docx", "pdf", "markdown", "txt"]
    section_count: int
    updated_at: AwareDatetime


class ExpertResponse(ApiModel):
    id: str
    name: str
    role: str | None


class ProjectDetailsResponse(ProjectSummaryResponse):
    challenge: str | None
    solution: str | None
    outcomes: list[str]
    capabilities: list[str]
    experts: list[ExpertResponse]
    documents: list[DocumentResponse]
    dna: ProjectDnaResponse | None


class QuestionRequest(ApiModel):
    question: str = Field(min_length=1, max_length=4_000)


class CitationResponse(ApiModel):
    citation_id: str
    project_id: str
    document_id: str
    filename: str
    section_sequence: int
    quote: str
    page_number: int | None
    slide_number: int | None
    heading: str | None


class AnswerClaimResponse(ApiModel):
    text: str
    citation_ids: list[str]


class ConfidenceBreakdownResponse(ApiModel):
    retrieval_strength: float
    citation_coverage: float
    source_diversity: float


class ConfidenceResponse(ApiModel):
    score: float
    band: Literal["high", "medium", "low"]
    breakdown: ConfidenceBreakdownResponse


class AnswerResponse(ApiModel):
    question: str
    answerable: bool
    answer: str | None
    claims: list[AnswerClaimResponse]
    citations: list[CitationResponse]
    confidence: ConfidenceResponse
    reason: str | None


class SearchResponse(ApiModel):
    answer: AnswerResponse
    related_projects: list[ProjectSummaryResponse]


class SimilaritySignalResponse(ApiModel):
    kind: str
    value: str


class SimilarProjectResponse(ApiModel):
    project_id: str
    display_name: str
    score: float
    shared_signals: list[SimilaritySignalResponse]


class SimilarProjectsResponse(ApiModel):
    projects: list[SimilarProjectResponse]


class ExpertSearchRequest(ApiModel):
    query: str = Field(min_length=1, max_length=2_000)


class ExpertEvidenceResponse(ApiModel):
    document_id: str
    section_sequence: int
    quote: str


class ExpertMatchResponse(ApiModel):
    expert_id: str
    name: str
    score: float
    project_ids: list[str]
    matched_signals: list[SimilaritySignalResponse]
    evidence: list[ExpertEvidenceResponse]


class ExpertSearchResponse(ApiModel):
    experts: list[ExpertMatchResponse]


class GenerateProposalRequest(ApiModel):
    request_id: str = Field(min_length=1, max_length=255)
    project_ids: list[str] = Field(min_length=1, max_length=20)
    client_name: str = Field(min_length=1, max_length=20_000)
    audience: str = Field(min_length=1, max_length=20_000)
    opportunity: str = Field(min_length=1, max_length=20_000)
    objectives: list[str] = Field(min_length=1, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)


class GenerateOnePagerRequest(ApiModel):
    request_id: str = Field(min_length=1, max_length=255)
    project_id: str = Field(min_length=1, max_length=255)
    audience: str = Field(min_length=1, max_length=20_000)


class ArtifactCitationResponse(ApiModel):
    source_id: str
    quote: str
    source_kind: str | None
    project_id: str | None
    document_id: str | None
    section_sequence: int | None
    filename: str | None


class ArtifactStatementResponse(ApiModel):
    text: str
    citations: list[ArtifactCitationResponse]


class ArtifactSectionResponse(ApiModel):
    key: str
    heading: str
    statements: list[ArtifactStatementResponse]


class BusinessArtifactResponse(ApiModel):
    artifact_id: str
    kind: Literal["proposal", "project_one_pager"]
    source_project_ids: list[str]
    title: str
    subtitle: str | None
    sections: list[ArtifactSectionResponse]
    status: Literal["draft"]
    model: str
    prompt_version: str
    created_at: AwareDatetime
