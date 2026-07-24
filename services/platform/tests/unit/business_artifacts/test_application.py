"""Proposal, one-pager, and PDF export application tests."""

import pytest

from blend_brain.business_artifacts.application import (
    GenerateOnePagerCommand,
    GenerateProposalCommand,
    GenerationLimits,
    OnePagerGenerationService,
    PdfExportService,
    ProposalGenerationService,
)
from blend_brain.business_artifacts.domain import (
    ArtifactActor,
    ArtifactAuthorizationError,
    ArtifactDraft,
    ArtifactExportError,
    ArtifactKind,
    ArtifactNotFoundError,
    ArtifactPermission,
    ArtifactPersistenceError,
    ArtifactRequestError,
    ArtifactScope,
    ArtifactSection,
    ArtifactSourceError,
    ArtifactStatement,
    ProjectOnePagerArtifact,
    ProposalArtifact,
)
from tests.unit.business_artifacts.helpers import (
    FixedClock,
    Generator,
    ObjectStore,
    Repository,
    SequenceIdentifiers,
    one_pager,
    proposal,
)


def actor(*permissions: ArtifactPermission) -> ArtifactActor:
    """Build an authorized test actor."""
    return ArtifactActor("employee-1", frozenset(permissions))


def scope() -> ArtifactScope:
    """Return one authorized project."""
    return ArtifactScope(("project-1",))


def proposal_command() -> GenerateProposalCommand:
    """Return a complete request."""
    return GenerateProposalCommand(
        request_id="request-1",
        project_ids=("project-1",),
        client_name="Example Co",
        audience="Executive team",
        opportunity="Improve forecasting",
        objectives=("Reduce planning time",),
        constraints=("Use existing data platform",),
    )


def test_proposal_generation_adds_brief_sources_and_persists_draft() -> None:
    repository = Repository()
    generator = Generator()
    service = ProposalGenerationService(generator, repository, FixedClock())

    result = service.generate(
        proposal_command(),
        actor=actor(ArtifactPermission.GENERATE),
        scope=scope(),
    )

    assert isinstance(result, ProposalArtifact)
    assert result.content_sha256
    assert result.source_project_ids == ("project-1",)
    assert repository.persisted == [result]
    assert tuple(source.source_id for source in generator.sources[:6]) == (
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "P1",
    )


def test_generation_is_idempotent_and_one_pager_is_project_scoped() -> None:
    repository = Repository()
    repository.existing = proposal()
    generator = Generator()
    proposal_service = ProposalGenerationService(generator, repository, FixedClock())
    assert (
        proposal_service.generate(
            proposal_command(),
            actor=actor(ArtifactPermission.GENERATE),
            scope=scope(),
        )
        is repository.existing
    )
    assert not repository.persisted
    assert not generator.sources

    repository.existing = None
    result = OnePagerGenerationService(generator, repository, FixedClock()).generate(
        GenerateOnePagerCommand("request-2", "project-1", "Sales"),
        actor=actor(ArtifactPermission.GENERATE),
        scope=scope(),
    )
    assert isinstance(result, ProjectOnePagerArtifact)
    assert generator.sources[0].source_id == "B1"
    assert generator.sources[1].source_id == "P1"


def test_generation_rejects_unauthorized_invalid_and_missing_source_requests() -> None:
    repository = Repository()
    service = ProposalGenerationService(
        Generator(), repository, FixedClock(), GenerationLimits(50, 1, 1)
    )
    with pytest.raises(ArtifactAuthorizationError):
        service.generate(proposal_command(), actor=actor(), scope=scope())
    with pytest.raises(ArtifactRequestError, match="objective"):
        service.generate(
            GenerateProposalCommand(
                "request", ("project-1",), "Client", "Audience", "Opportunity", ()
            ),
            actor=actor(ArtifactPermission.GENERATE),
            scope=scope(),
        )
    repository.sources = ()
    with pytest.raises(ArtifactSourceError, match="empty"):
        service.generate(
            proposal_command(),
            actor=actor(ArtifactPermission.GENERATE),
            scope=scope(),
        )
    with pytest.raises(ValueError, match="greater than zero"):
        GenerationLimits(max_projects=0)

    invalid_template = ArtifactDraft(
        "Title",
        None,
        (ArtifactSection("invalid", "Invalid", ()),),
        "model",
        "prompt",
    )
    with pytest.raises(ArtifactSourceError, match="template"):
        ProposalGenerationService(Generator(invalid_template), Repository(), FixedClock()).generate(
            proposal_command(),
            actor=actor(ArtifactPermission.GENERATE),
            scope=scope(),
        )

    uncited = ArtifactDraft(
        "Title",
        None,
        tuple(
            ArtifactSection(key, key, (ArtifactStatement("Claim", ()),))
            for key in (
                "executive_summary",
                "client_needs",
                "proposed_approach",
                "relevant_experience",
                "differentiators",
                "expected_outcomes",
                "next_steps",
            )
        ),
        "model",
        "prompt",
    )
    with pytest.raises(ArtifactSourceError, match="citations"):
        ProposalGenerationService(Generator(uncited), Repository(), FixedClock()).generate(
            proposal_command(),
            actor=actor(ArtifactPermission.GENERATE),
            scope=scope(),
        )


class Renderer:
    """Configurable PDF renderer fake."""

    def __init__(self, content: bytes = b"%PDF-1.7\ncontent") -> None:
        self.content = content

    def render(self, _artifact: object) -> bytes:
        """Return configured bytes."""
        return self.content


def test_pdf_export_stores_private_object_and_records_metadata() -> None:
    repository = Repository()
    repository.existing = one_pager()
    store = ObjectStore()
    service = PdfExportService(
        repository,
        Renderer(),
        store,
        FixedClock(),
        SequenceIdentifiers(),
    )

    result = service.export(
        "one-pager-1",
        ArtifactKind.PROJECT_ONE_PAGER,
        actor=actor(ArtifactPermission.EXPORT),
        scope=scope(),
    )

    assert result.storage_location == "local-test-store"
    assert result.sha256
    assert result.object_key in store.objects
    assert repository.exports == [result]


def test_pdf_export_enforces_scope_format_bounds_and_compensates() -> None:
    repository = Repository()
    service = PdfExportService(
        repository,
        Renderer(b"invalid"),
        ObjectStore(),
        FixedClock(),
        SequenceIdentifiers(),
        max_pdf_bytes=20,
    )
    with pytest.raises(ArtifactAuthorizationError):
        service.export("id", ArtifactKind.PROPOSAL, actor=actor(), scope=scope())
    with pytest.raises(ArtifactNotFoundError):
        service.export(
            "id",
            ArtifactKind.PROPOSAL,
            actor=actor(ArtifactPermission.EXPORT),
            scope=scope(),
        )
    repository.existing = proposal()
    with pytest.raises(ArtifactExportError, match="invalid"):
        service.export(
            "artifact-1",
            ArtifactKind.PROPOSAL,
            actor=actor(ArtifactPermission.EXPORT),
            scope=scope(),
        )

    store = ObjectStore()
    repository.record_error = ArtifactPersistenceError("failed")
    compensated = PdfExportService(
        repository,
        Renderer(),
        store,
        FixedClock(),
        SequenceIdentifiers(),
    )
    with pytest.raises(ArtifactPersistenceError):
        compensated.export(
            "artifact-1",
            ArtifactKind.PROPOSAL,
            actor=actor(ArtifactPermission.EXPORT),
            scope=scope(),
        )
    assert store.deleted

    store.delete_error = RuntimeError("cleanup failed")
    with pytest.raises(ArtifactExportError, match="cleanup"):
        compensated.export(
            "artifact-1",
            ArtifactKind.PROPOSAL,
            actor=actor(ArtifactPermission.EXPORT),
            scope=scope(),
        )


def test_artifact_domain_and_export_configuration_validate() -> None:
    with pytest.raises(ValueError, match="actor_id"):
        ArtifactActor(" ", frozenset())
    with pytest.raises(ValueError, match="at least one"):
        ArtifactScope(())
    with pytest.raises(ValueError, match="greater than zero"):
        PdfExportService(
            Repository(),
            Renderer(),
            ObjectStore(),
            FixedClock(),
            SequenceIdentifiers(),
            max_pdf_bytes=0,
        )
