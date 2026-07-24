"""Typed Phase 8 builders and test doubles."""

from __future__ import annotations

from datetime import UTC, datetime

from blend_brain.business_artifacts.application.ports import StoredObject
from blend_brain.business_artifacts.domain import (
    ArtifactDraft,
    ArtifactExport,
    ArtifactKind,
    ArtifactScope,
    ArtifactSection,
    ArtifactSource,
    ArtifactSourceKind,
    ArtifactStatement,
    ArtifactStatus,
    BusinessArtifact,
    OnePagerBrief,
    ProjectOnePagerArtifact,
    ProposalArtifact,
    ProposalBrief,
)

NOW = datetime(2026, 7, 24, 16, 0, tzinfo=UTC)


def project_source(project_id: str = "project-1") -> ArtifactSource:
    """Return one grounded project source."""
    return ArtifactSource(
        "P1",
        ArtifactSourceKind.PROJECT_DOCUMENT,
        "Blend delivered a forecasting platform that reduced planning time by 30%.",
        project_id=project_id,
        document_id="document-1",
        section_sequence=2,
        filename="case-study.md",
    )


def draft() -> ArtifactDraft:
    """Return a concise grounded draft."""
    from blend_brain.business_artifacts.domain import ArtifactCitation

    return ArtifactDraft(
        title="Forecasting Transformation",
        subtitle="AI-generated draft",
        sections=(
            ArtifactSection(
                "overview",
                "Overview",
                (
                    ArtifactStatement(
                        "Blend delivered a forecasting platform.",
                        (ArtifactCitation("P1", "delivered a forecasting platform"),),
                    ),
                ),
            ),
        ),
        model="gpt-4.1-2025-04-14",
        prompt_version="test-v1",
    )


def proposal() -> ProposalArtifact:
    """Return a persisted proposal artifact."""
    item = draft()
    return ProposalArtifact(
        artifact_id="artifact-1",
        request_id="request-1",
        source_project_ids=("project-1",),
        brief=ProposalBrief(
            "Example Co",
            "Executive team",
            "Improve forecasting",
            ("Reduce planning time",),
            (),
        ),
        title=item.title,
        subtitle=item.subtitle,
        sections=item.sections,
        model=item.model,
        prompt_version=item.prompt_version,
        status=ArtifactStatus.DRAFT,
        content_sha256="a" * 64,
        created_by="employee-1",
        created_at=NOW,
    )


def one_pager(*, sections: tuple[ArtifactSection, ...] | None = None) -> ProjectOnePagerArtifact:
    """Return a persisted project one-pager artifact."""
    item = draft()
    return ProjectOnePagerArtifact(
        artifact_id="one-pager-1",
        request_id="request-2",
        source_project_ids=("project-1",),
        brief=OnePagerBrief("project-1", "Sales"),
        title=item.title,
        subtitle=item.subtitle,
        sections=sections if sections is not None else item.sections,
        model=item.model,
        prompt_version=item.prompt_version,
        status=ArtifactStatus.DRAFT,
        content_sha256="b" * 64,
        created_by="employee-1",
        created_at=NOW,
    )


class FixedClock:
    """Deterministic application clock."""

    def now(self) -> datetime:
        """Return test time."""
        return NOW


class SequenceIdentifiers:
    """Return stable readable IDs."""

    def __init__(self) -> None:
        self.count = 0

    def new(self) -> str:
        """Return the next ID."""
        self.count += 1
        return f"export-{self.count}"


class Generator:
    """Capture generation inputs and return a configured draft."""

    def __init__(self, result: ArtifactDraft | None = None) -> None:
        self.result = result or draft()
        self.sources: tuple[ArtifactSource, ...] = ()

    def generate_proposal(
        self, _brief: ProposalBrief, sources: tuple[ArtifactSource, ...]
    ) -> ArtifactDraft:
        """Return the configured proposal draft."""
        self.sources = sources
        return self._template(
            (
                "executive_summary",
                "client_needs",
                "proposed_approach",
                "relevant_experience",
                "differentiators",
                "expected_outcomes",
                "next_steps",
            )
        )

    def generate_one_pager(
        self, _brief: OnePagerBrief, sources: tuple[ArtifactSource, ...]
    ) -> ArtifactDraft:
        """Return the configured one-pager draft."""
        self.sources = sources
        return self._template(
            (
                "executive_summary",
                "the_challenge",
                "our_solution",
                "key_features",
                "quantified_outcomes",
                "business_value",
                "known_gaps_caveats",
                "sources_used",
            )
        )

    def _template(self, keys: tuple[str, ...]) -> ArtifactDraft:
        if tuple(section.key for section in self.result.sections) != ("overview",):
            return self.result
        statements = self.result.sections[0].statements
        return ArtifactDraft(
            self.result.title,
            self.result.subtitle,
            tuple(ArtifactSection(key, key.replace("_", " ").title(), statements) for key in keys),
            self.result.model,
            self.result.prompt_version,
        )


class Repository:
    """In-memory Phase 8 repository contract fake."""

    def __init__(self) -> None:
        self.sources: tuple[ArtifactSource, ...] = (project_source(),)
        self.existing: BusinessArtifact | None = None
        self.persisted: list[BusinessArtifact] = []
        self.exports: list[ArtifactExport] = []
        self.record_error: Exception | None = None

    def load_project_sources(self, _project_ids: tuple[str, ...]) -> tuple[ArtifactSource, ...]:
        """Return configured sources."""
        return self.sources

    def find_by_request(
        self,
        _request_id: str,
        _kind: ArtifactKind,
        _created_by: str,
        _project_ids: tuple[str, ...],
    ) -> BusinessArtifact | None:
        """Return configured idempotent result."""
        return self.existing

    def persist(self, artifact: BusinessArtifact, _sources: tuple[ArtifactSource, ...]) -> None:
        """Record a generated artifact."""
        self.persisted.append(artifact)

    def get_artifact(
        self, _artifact_id: str, _kind: ArtifactKind, _scope: ArtifactScope
    ) -> BusinessArtifact | None:
        """Return configured artifact."""
        return self.existing

    def record_export(self, export: ArtifactExport) -> None:
        """Record metadata or raise a configured failure."""
        if self.record_error:
            raise self.record_error
        self.exports.append(export)


class ObjectStore:
    """In-memory private object store fake."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.delete_error: Exception | None = None

    def put(self, key: str, content: bytes, _content_type: str) -> StoredObject:
        """Store bytes."""
        self.objects[key] = content
        return StoredObject("local-test-store", key)

    def delete(self, key: str) -> None:
        """Delete bytes or raise a configured failure."""
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(key)
        self.objects.pop(key, None)
