"""Knowledge-gap detection tests."""

from dataclasses import replace

import pytest

from blend_brain.knowledge_enrichment.domain import ClaimConfidence, GroundedClaim
from blend_brain.knowledge_lifecycle.application import (
    FieldPolicy,
    KnowledgeGapDetectionService,
    KnowledgeGapDetector,
)
from blend_brain.knowledge_lifecycle.domain import GapField, GapKind, GapSeverity
from tests.unit.knowledge_enrichment.helpers import NOW, claim, dna
from tests.unit.knowledge_lifecycle.helpers import FixedClock, MemoryRepository


def test_detector_finds_missing_and_low_confidence_fields_deterministically() -> None:
    low = GroundedClaim("Retail", ClaimConfidence.LOW, claim().evidence)
    project_dna = replace(dna(), industry=low)
    detector = KnowledgeGapDetector()

    first = detector.detect(project_dna, detected_at=NOW)
    second = detector.detect(project_dna, detected_at=NOW)

    industry = next(gap for gap in first.gaps if gap.field is GapField.INDUSTRY)
    client = next(gap for gap in first.gaps if gap.field is GapField.CLIENT_NAME)
    assert first.assessment_id == second.assessment_id
    assert tuple(gap.gap_id for gap in first.gaps) == tuple(gap.gap_id for gap in second.gaps)
    assert industry.kind is GapKind.LOW_CONFIDENCE
    assert industry.observed_values == ("Retail",)
    assert client.kind is GapKind.MISSING
    assert any(gap.severity is GapSeverity.CRITICAL for gap in first.gaps) is False


def test_detector_uses_policy_priority_and_service_persists() -> None:
    repository = MemoryRepository()
    detector = KnowledgeGapDetector((FieldPolicy(GapField.CLIENT_NAME, GapSeverity.CRITICAL),))
    service = KnowledgeGapDetectionService(detector, repository, FixedClock())

    assessment = service.assess(dna())

    assert assessment.gaps[0].severity is GapSeverity.CRITICAL
    assert repository.assessments == [assessment]


def test_detector_rejects_invalid_policy_and_naive_time() -> None:
    policy = FieldPolicy(GapField.CLIENT_NAME, GapSeverity.HIGH)
    with pytest.raises(ValueError, match="unique"):
        KnowledgeGapDetector((policy, policy))
    with pytest.raises(ValueError, match="timezone-aware"):
        KnowledgeGapDetector().detect(dna(), detected_at=NOW.replace(tzinfo=None))
