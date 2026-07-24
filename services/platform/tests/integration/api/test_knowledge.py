"""Authenticated knowledge API contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from fastapi.testclient import TestClient

from blend_brain.bootstrap.application import create_app
from blend_brain.entrypoints.api.auth import StaticBearerAuthenticator
from blend_brain.knowledge_catalog.application import KnowledgeCatalogService
from blend_brain.knowledge_catalog.domain import (
    CatalogDocument,
    CatalogProject,
    DashboardSnapshot,
    IndustryCount,
)
from blend_brain.knowledge_retrieval.domain import (
    AnswerCitation,
    AnswerConfidence,
    ConfidenceBand,
    ConfidenceBreakdown,
    GroundedAnswer,
    GroundedAnswerClaim,
)
from blend_brain.organizational_intelligence.domain import (
    ExpertMatch,
    GraphEvidence,
    NodeType,
    SimilaritySignal,
    SimilarProject,
)
from tests.unit.business_artifacts.helpers import one_pager, proposal
from tests.unit.knowledge_enrichment.helpers import dna

if TYPE_CHECKING:
    from blend_brain.bootstrap.configuration import Settings
    from blend_brain.business_artifacts.domain import ArtifactKind
    from blend_brain.entrypoints.api.services import KnowledgeApiServices

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)
AUTHORIZATION = {"Authorization": "Bearer test-token"}


class CatalogRepository:
    def __init__(self) -> None:
        self.item = CatalogProject(
            project_id="project-1",
            display_name="Retail Forecasting",
            updated_at=NOW,
            dna=dna(),
            document_count=1,
            documents=(CatalogDocument("document-id", "project.md", "markdown", 2, NOW),),
            section_locations=((1, None, None, "Overview"),),
        )

    def all_project_ids(self) -> tuple[str, ...]:
        return ("project-1",)

    def dashboard(self, project_ids: tuple[str, ...]) -> DashboardSnapshot:
        assert project_ids == ("project-1",)
        return DashboardSnapshot(1, 1, 0, 1.0, (self.item,), (IndustryCount("Retail", 1),), NOW)

    def project(self, project_id: str, project_ids: tuple[str, ...]) -> CatalogProject | None:
        return self.item if project_id in project_ids else None

    def projects(
        self, requested_ids: tuple[str, ...], project_ids: tuple[str, ...]
    ) -> tuple[CatalogProject, ...]:
        return (self.item,) if "project-1" in requested_ids and "project-1" in project_ids else ()


class Answering:
    def ask(self, question: str, _scope: object) -> GroundedAnswer:
        return GroundedAnswer(
            question=question,
            answerable=True,
            answer="Planning time improved.",
            claims=(GroundedAnswerClaim("Planning time improved.", ("C1",)),),
            citations=(
                AnswerCitation(
                    "C1", "project-1", "document-id", "project.md", 1, "Retail Forecasting"
                ),
            ),
            confidence=AnswerConfidence(
                0.9, ConfidenceBand.HIGH, ConfidenceBreakdown(0.9, 1.0, 1.0)
            ),
        )


class Similarity:
    def find_similar(
        self, _project_id: str, _scope: object, *, limit: int
    ) -> tuple[SimilarProject, ...]:
        assert limit == 6
        return (
            SimilarProject(
                "project-2",
                "Related Project",
                0.82,
                (SimilaritySignal(NodeType.INDUSTRY, "Retail"),),
            ),
        )


class Experts:
    def find(self, _query: str, _scope: object) -> tuple[ExpertMatch, ...]:
        return (
            ExpertMatch(
                "expert-1",
                "Jane Expert",
                0.91,
                ("project-1",),
                (SimilaritySignal(NodeType.TECHNOLOGY, "Snowflake"),),
                (GraphEvidence("document-id", 1, "Jane Expert led delivery"),),
            ),
        )


class ArtifactGenerator:
    def __init__(self, result: object) -> None:
        self.result = result

    def generate(self, _command: object, *, actor: object, scope: object) -> object:
        assert actor is not None
        assert scope is not None
        return self.result


class PdfExports:
    def export(
        self,
        _artifact_id: str,
        _kind: ArtifactKind,
        *,
        _actor: object,
        _scope: object,
    ) -> None:
        raise AssertionError("PDF export is not used in this contract test")


def _client(settings: Settings) -> TestClient:
    catalog = KnowledgeCatalogService(CatalogRepository())
    services = SimpleNamespace(
        authenticator=StaticBearerAuthenticator(
            enabled=True,
            token="test-token",  # noqa: S106 - isolated test credential
            subject="tester",
            project_ids=("*",),
        ),
        catalog=catalog,
        question_answering=Answering(),
        project_similarity=Similarity(),
        expert_finder=Experts(),
        retrieval_indexes=object(),
        intelligence_indexes=object(),
        knowledge_graph=object(),
        artifacts=SimpleNamespace(
            proposals=ArtifactGenerator(proposal()),
            one_pagers=ArtifactGenerator(one_pager()),
            pdf_exports=PdfExports(),
        ),
    )
    return TestClient(create_app(settings, cast("KnowledgeApiServices", cast("Any", services))))


def test_requires_valid_bearer_authentication(settings: Settings) -> None:
    with _client(settings) as client:
        assert client.get("/api/v1/dashboard").status_code == HTTPStatus.UNAUTHORIZED
        assert (
            client.get("/api/v1/dashboard", headers={"Authorization": "Bearer wrong"}).status_code
            == HTTPStatus.UNAUTHORIZED
        )


def test_dashboard_project_and_dna_contracts(settings: Settings) -> None:
    with _client(settings) as client:
        dashboard = client.get("/api/v1/dashboard", headers=AUTHORIZATION)
        project = client.get("/api/v1/projects/project-1", headers=AUTHORIZATION)
        project_dna = client.get("/api/v1/projects/project-1/dna", headers=AUTHORIZATION)
        missing = client.get("/api/v1/projects/secret", headers=AUTHORIZATION)

    assert dashboard.status_code == HTTPStatus.OK
    assert dashboard.json()["totalProjects"] == 1
    assert project.json()["documents"][0]["format"] == "markdown"
    assert project_dna.json()["technologies"][0]["value"] == "Snowflake"
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_question_similarity_and_expert_contracts(settings: Settings) -> None:
    with _client(settings) as client:
        answer = client.post(
            "/api/v1/questions", json={"question": "What improved?"}, headers=AUTHORIZATION
        )
        similar = client.get("/api/v1/projects/project-1/similar", headers=AUTHORIZATION)
        experts = client.post(
            "/api/v1/experts/search",
            json={"query": "Snowflake"},
            headers=AUTHORIZATION,
        )

    assert answer.json()["answer"]["citations"][0]["projectId"] == "project-1"
    assert similar.json()["projects"][0]["sharedSignals"][0]["value"] == "Retail"
    assert experts.json()["experts"][0]["evidence"][0]["documentId"] == "document-id"


def test_proposal_and_pih_sales_brief_contracts(settings: Settings) -> None:
    with _client(settings) as client:
        proposal_response = client.post(
            "/api/v1/artifacts/proposals",
            headers=AUTHORIZATION,
            json={
                "requestId": "request-1",
                "projectIds": ["project-1"],
                "clientName": "Example Co",
                "audience": "Executives",
                "opportunity": "Improve forecasting",
                "objectives": ["Reduce planning time"],
                "constraints": [],
            },
        )
        one_pager_response = client.post(
            "/api/v1/artifacts/one-pagers",
            headers=AUTHORIZATION,
            json={
                "requestId": "request-2",
                "projectId": "project-1",
                "audience": "Sales",
            },
        )

    assert proposal_response.status_code == HTTPStatus.OK
    assert proposal_response.json()["kind"] == "proposal"
    assert one_pager_response.status_code == HTTPStatus.OK
    assert one_pager_response.json()["kind"] == "project_one_pager"
