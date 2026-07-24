"""Deterministic Project DNA knowledge-gap detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from blend_brain.knowledge_enrichment.domain import ClaimConfidence, GroundedClaim, ProjectDNA
from blend_brain.knowledge_lifecycle.domain import (
    GapAssessment,
    GapField,
    GapKind,
    GapSeverity,
    GapStatus,
    KnowledgeGap,
)

if TYPE_CHECKING:
    from datetime import datetime

    from .ports import Clock, KnowledgeLifecycleRepository

GAP_POLICY_VERSION = 1


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    """Business priority for one required Project DNA field."""

    field: GapField
    missing_severity: GapSeverity
    low_confidence_severity: GapSeverity = GapSeverity.MEDIUM


DEFAULT_FIELD_POLICIES = (
    FieldPolicy(GapField.PROJECT_NAME, GapSeverity.MEDIUM),
    FieldPolicy(GapField.CLIENT_NAME, GapSeverity.HIGH),
    FieldPolicy(GapField.INDUSTRY, GapSeverity.HIGH),
    FieldPolicy(GapField.ENGAGEMENT_TYPE, GapSeverity.MEDIUM),
    FieldPolicy(GapField.SUMMARY, GapSeverity.HIGH),
    FieldPolicy(GapField.BUSINESS_CHALLENGES, GapSeverity.HIGH),
    FieldPolicy(GapField.USE_CASES, GapSeverity.HIGH),
    FieldPolicy(GapField.CAPABILITIES, GapSeverity.HIGH),
    FieldPolicy(GapField.TECHNOLOGIES, GapSeverity.MEDIUM),
    FieldPolicy(GapField.DATA_SOURCES, GapSeverity.LOW),
    FieldPolicy(GapField.CLOUD_PLATFORMS, GapSeverity.LOW),
    FieldPolicy(GapField.OUTCOMES, GapSeverity.CRITICAL),
    FieldPolicy(GapField.DIFFERENTIATORS, GapSeverity.MEDIUM),
    FieldPolicy(GapField.EXPERTS, GapSeverity.HIGH),
)


class KnowledgeGapDetector:
    """Detect missing and low-confidence knowledge without inventing facts."""

    def __init__(self, policies: tuple[FieldPolicy, ...] = DEFAULT_FIELD_POLICIES) -> None:
        fields = tuple(policy.field for policy in policies)
        if not fields or len(set(fields)) != len(fields):
            raise ValueError("Gap policies must contain unique fields")
        self._policies = policies

    def detect(self, dna: ProjectDNA, *, detected_at: datetime) -> GapAssessment:
        """Build a stable assessment for the supplied Project DNA version."""
        if detected_at.tzinfo is None:
            raise ValueError("detected_at must be a timezone-aware datetime")
        gaps: list[KnowledgeGap] = []
        for policy in self._policies:
            claims = self._claims(dna, policy.field)
            if not claims:
                gaps.append(
                    self._gap(
                        dna,
                        policy,
                        GapKind.MISSING,
                        policy.missing_severity,
                        (),
                        detected_at,
                    )
                )
                continue
            low_confidence = tuple(
                claim.value for claim in claims if claim.confidence is ClaimConfidence.LOW
            )
            if low_confidence:
                gaps.append(
                    self._gap(
                        dna,
                        policy,
                        GapKind.LOW_CONFIDENCE,
                        policy.low_confidence_severity,
                        low_confidence,
                        detected_at,
                    )
                )
        assessment_id = str(
            uuid5(
                NAMESPACE_URL,
                f"blend-brain:gaps:{dna.dna_id}:v{GAP_POLICY_VERSION}",
            )
        )
        return GapAssessment(
            assessment_id=assessment_id,
            policy_version=GAP_POLICY_VERSION,
            project_id=dna.project_id,
            dna_id=dna.dna_id,
            gaps=tuple(gaps),
            detected_at=detected_at,
        )

    @staticmethod
    def _claims(dna: ProjectDNA, field: GapField) -> tuple[GroundedClaim, ...]:
        values: dict[GapField, GroundedClaim | tuple[GroundedClaim, ...] | None] = {
            GapField.PROJECT_NAME: dna.project_name,
            GapField.CLIENT_NAME: dna.client_name,
            GapField.INDUSTRY: dna.industry,
            GapField.ENGAGEMENT_TYPE: dna.engagement_type,
            GapField.SUMMARY: dna.summary,
            GapField.BUSINESS_CHALLENGES: dna.business_challenges,
            GapField.USE_CASES: dna.use_cases,
            GapField.CAPABILITIES: dna.capabilities,
            GapField.TECHNOLOGIES: dna.technologies,
            GapField.DATA_SOURCES: dna.data_sources,
            GapField.CLOUD_PLATFORMS: dna.cloud_platforms,
            GapField.OUTCOMES: dna.outcomes,
            GapField.DIFFERENTIATORS: dna.differentiators,
            GapField.EXPERTS: dna.experts,
        }
        value = values[field]
        if value is None:
            return ()
        if isinstance(value, GroundedClaim):
            return (value,)
        return value

    @staticmethod
    def _gap(
        dna: ProjectDNA,
        policy: FieldPolicy,
        kind: GapKind,
        severity: GapSeverity,
        observed_values: tuple[str, ...],
        detected_at: datetime,
    ) -> KnowledgeGap:
        gap_id = str(
            uuid5(
                NAMESPACE_URL,
                f"blend-brain:gap:{dna.dna_id}:{policy.field.value}:{kind.value}:v{GAP_POLICY_VERSION}",
            )
        )
        explanation = (
            f"Project DNA does not contain {policy.field.value.replace('_', ' ')}."
            if kind is GapKind.MISSING
            else f"Project DNA contains low-confidence {policy.field.value.replace('_', ' ')}."
        )
        return KnowledgeGap(
            gap_id=gap_id,
            project_id=dna.project_id,
            dna_id=dna.dna_id,
            field=policy.field,
            kind=kind,
            severity=severity,
            explanation=explanation,
            observed_values=observed_values,
            status=GapStatus.OPEN,
            detected_at=detected_at,
        )


class KnowledgeGapDetectionService:
    """Detect and atomically persist a complete assessment."""

    def __init__(
        self,
        detector: KnowledgeGapDetector,
        repository: KnowledgeLifecycleRepository,
        clock: Clock,
    ) -> None:
        self._detector = detector
        self._repository = repository
        self._clock = clock

    def assess(self, dna: ProjectDNA) -> GapAssessment:
        """Assess one DNA version and persist its replaceable snapshot."""
        assessment = self._detector.detect(dna, detected_at=self._clock.now())
        self._repository.replace_assessment(assessment)
        return assessment
