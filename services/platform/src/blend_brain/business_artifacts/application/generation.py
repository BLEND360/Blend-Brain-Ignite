"""Grounded proposal and one-pager generation use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from blend_brain.business_artifacts.domain import (
    ArtifactActor,
    ArtifactAuthorizationError,
    ArtifactDraft,
    ArtifactKind,
    ArtifactPermission,
    ArtifactRequestError,
    ArtifactScope,
    ArtifactSource,
    ArtifactSourceError,
    ArtifactSourceKind,
    ArtifactStatus,
    OnePagerBrief,
    ProjectOnePagerArtifact,
    ProposalArtifact,
    ProposalBrief,
    artifact_content_sha256,
)

PROPOSAL_SECTION_KEYS = (
    "executive_summary",
    "client_needs",
    "proposed_approach",
    "relevant_experience",
    "differentiators",
    "expected_outcomes",
    "next_steps",
)
ONE_PAGER_SECTION_KEYS = (
    "executive_summary",
    "the_challenge",
    "our_solution",
    "key_features",
    "quantified_outcomes",
    "business_value",
    "known_gaps_caveats",
    "sources_used",
)

if TYPE_CHECKING:
    from blend_brain.business_artifacts.application.ports import (
        BusinessArtifactGenerator,
        BusinessArtifactRepository,
        Clock,
    )


@dataclass(frozen=True, slots=True)
class GenerationLimits:
    """Bound requests and source-corpus expansion."""

    max_brief_characters: int = 20_000
    max_projects: int = 20
    max_project_sources: int = 500
    max_generated_characters: int = 100_000

    def __post_init__(self) -> None:
        if (
            min(
                self.max_brief_characters,
                self.max_projects,
                self.max_project_sources,
                self.max_generated_characters,
            )
            <= 0
        ):
            raise ValueError("Generation limits must be greater than zero")


@dataclass(frozen=True, slots=True)
class GenerateProposalCommand:
    """Input for one idempotent proposal generation request."""

    request_id: str
    project_ids: tuple[str, ...]
    client_name: str
    audience: str
    opportunity: str
    objectives: tuple[str, ...]
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GenerateOnePagerCommand:
    """Input for one idempotent project one-pager request."""

    request_id: str
    project_id: str
    audience: str


class _GenerationBase:
    def __init__(
        self,
        generator: BusinessArtifactGenerator,
        repository: BusinessArtifactRepository,
        clock: Clock,
        limits: GenerationLimits | None = None,
    ) -> None:
        self._generator = generator
        self._repository = repository
        self._clock = clock
        self._limits = limits or GenerationLimits()

    @staticmethod
    def _authorize(
        actor: ArtifactActor, scope: ArtifactScope, project_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        normalized = tuple(sorted({item.strip() for item in project_ids if item.strip()}))
        if (
            ArtifactPermission.GENERATE not in actor.permissions
            or not normalized
            or not scope.contains_all(normalized)
        ):
            raise ArtifactAuthorizationError("Actor is not authorized to generate this artifact")
        return normalized

    @staticmethod
    def _required(value: str, field: str, limit: int) -> str:
        normalized = value.strip()
        if not normalized:
            raise ArtifactRequestError(f"{field} cannot be empty")
        if len(normalized) > limit:
            raise ArtifactRequestError(f"{field} exceeds the configured character limit")
        return normalized

    def _values(self, values: tuple[str, ...], field: str) -> tuple[str, ...]:
        normalized = tuple(
            self._required(value, field, self._limits.max_brief_characters) for value in values
        )
        if sum(len(value) for value in normalized) > self._limits.max_brief_characters:
            raise ArtifactRequestError(f"{field} exceeds the configured total character limit")
        return normalized

    def _project_sources(self, project_ids: tuple[str, ...]) -> tuple[ArtifactSource, ...]:
        sources = self._repository.load_project_sources(project_ids)
        if not sources or len(sources) > self._limits.max_project_sources:
            raise ArtifactSourceError(
                "Authorized artifact source corpus is empty or exceeds its configured limit",
                project_count=len(project_ids),
            )
        covered = {source.project_id for source in sources if source.project_id}
        if not set(project_ids).issubset(covered):
            raise ArtifactSourceError(
                "One or more requested projects have no current source material",
                project_count=len(project_ids),
            )
        return sources

    def _validate_draft(self, draft: object, required_keys: tuple[str, ...]) -> None:
        if not isinstance(draft, ArtifactDraft):
            raise ArtifactSourceError("Artifact generator returned an invalid draft type")
        if tuple(section.key for section in draft.sections) != required_keys:
            raise ArtifactSourceError("Artifact generator returned an invalid section template")
        character_count = len(draft.title) + len(draft.subtitle or "")
        for section in draft.sections:
            character_count += len(section.heading)
            for statement in section.statements:
                if not statement.citations:
                    raise ArtifactSourceError("Artifact statement is missing grounded citations")
                character_count += len(statement.text)
        if character_count > self._limits.max_generated_characters:
            raise ArtifactSourceError("Generated artifact exceeds its configured character limit")

    @staticmethod
    def _artifact_id(
        kind: ArtifactKind,
        request_id: str,
        actor_id: str,
        project_ids: tuple[str, ...],
    ) -> str:
        identity = ":".join((kind.value, request_id, actor_id, *project_ids))
        return str(uuid5(NAMESPACE_URL, f"blend-brain:artifact:{identity}"))


class ProposalGenerationService(_GenerationBase):
    """Generate and atomically persist a grounded proposal draft."""

    def generate(
        self,
        command: GenerateProposalCommand,
        *,
        actor: ArtifactActor,
        scope: ArtifactScope,
    ) -> ProposalArtifact:
        """Return the existing idempotent result or generate a new draft."""
        project_ids = self._authorize(actor, scope, command.project_ids)
        if len(project_ids) > self._limits.max_projects:
            raise ArtifactRequestError("Proposal includes too many source projects")
        request_id = self._required(command.request_id, "request_id", 255)
        existing = self._repository.find_by_request(
            request_id, ArtifactKind.PROPOSAL, actor.actor_id, project_ids
        )
        if existing is not None:
            if not isinstance(existing, ProposalArtifact):
                raise ArtifactSourceError("Stored proposal request has an invalid artifact type")
            return existing
        brief = ProposalBrief(
            client_name=self._required(
                command.client_name, "client_name", self._limits.max_brief_characters
            ),
            audience=self._required(
                command.audience, "audience", self._limits.max_brief_characters
            ),
            opportunity=self._required(
                command.opportunity, "opportunity", self._limits.max_brief_characters
            ),
            objectives=self._values(command.objectives, "objective"),
            constraints=self._values(command.constraints, "constraint"),
        )
        if not brief.objectives:
            raise ArtifactRequestError("At least one proposal objective is required")
        sources = self._brief_sources(brief) + self._project_sources(project_ids)
        draft = self._generator.generate_proposal(brief, sources)
        self._validate_draft(draft, PROPOSAL_SECTION_KEYS)
        artifact = ProposalArtifact(
            artifact_id=self._artifact_id(
                ArtifactKind.PROPOSAL, request_id, actor.actor_id, project_ids
            ),
            request_id=request_id,
            source_project_ids=project_ids,
            brief=brief,
            title=draft.title,
            subtitle=draft.subtitle,
            sections=draft.sections,
            model=draft.model,
            prompt_version=draft.prompt_version,
            status=ArtifactStatus.DRAFT,
            content_sha256=artifact_content_sha256(draft),
            created_by=actor.actor_id,
            created_at=self._clock.now(),
        )
        self._repository.persist(artifact, sources)
        return artifact

    @staticmethod
    def _brief_sources(brief: ProposalBrief) -> tuple[ArtifactSource, ...]:
        values = [
            ("B1", f"Client: {brief.client_name}"),
            ("B2", f"Audience: {brief.audience}"),
            ("B3", f"Opportunity: {brief.opportunity}"),
        ]
        values.extend(
            (f"B{index}", f"Objective: {value}") for index, value in enumerate(brief.objectives, 4)
        )
        start = len(values) + 1
        values.extend(
            (f"B{index}", f"Constraint: {value}")
            for index, value in enumerate(brief.constraints, start)
        )
        return tuple(
            ArtifactSource(source_id, ArtifactSourceKind.USER_BRIEF, text)
            for source_id, text in values
        )


class OnePagerGenerationService(_GenerationBase):
    """Generate and atomically persist a grounded project one-pager draft."""

    def generate(
        self,
        command: GenerateOnePagerCommand,
        *,
        actor: ArtifactActor,
        scope: ArtifactScope,
    ) -> ProjectOnePagerArtifact:
        """Return the existing idempotent result or generate a new one-pager."""
        project_ids = self._authorize(actor, scope, (command.project_id,))
        request_id = self._required(command.request_id, "request_id", 255)
        existing = self._repository.find_by_request(
            request_id,
            ArtifactKind.PROJECT_ONE_PAGER,
            actor.actor_id,
            project_ids,
        )
        if existing is not None:
            if not isinstance(existing, ProjectOnePagerArtifact):
                raise ArtifactSourceError("Stored one-pager request has an invalid artifact type")
            return existing
        brief = OnePagerBrief(
            project_id=project_ids[0],
            audience=self._required(
                command.audience, "audience", self._limits.max_brief_characters
            ),
        )
        sources = (
            ArtifactSource("B1", ArtifactSourceKind.USER_BRIEF, f"Audience: {brief.audience}"),
            *self._project_sources(project_ids),
        )
        draft = self._generator.generate_one_pager(brief, sources)
        self._validate_draft(draft, ONE_PAGER_SECTION_KEYS)
        artifact = ProjectOnePagerArtifact(
            artifact_id=self._artifact_id(
                ArtifactKind.PROJECT_ONE_PAGER,
                request_id,
                actor.actor_id,
                project_ids,
            ),
            request_id=request_id,
            source_project_ids=project_ids,
            brief=brief,
            title=draft.title,
            subtitle=draft.subtitle,
            sections=draft.sections,
            model=draft.model,
            prompt_version=draft.prompt_version,
            status=ArtifactStatus.DRAFT,
            content_sha256=artifact_content_sha256(draft),
            created_by=actor.actor_id,
            created_at=self._clock.now(),
        )
        self._repository.persist(artifact, sources)
        return artifact
