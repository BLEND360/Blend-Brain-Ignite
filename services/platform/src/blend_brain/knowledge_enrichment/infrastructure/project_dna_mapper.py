"""Strict deserialization of persisted Project DNA JSON."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from blend_brain.knowledge_enrichment.domain import (
    ClaimConfidence,
    EvidenceReference,
    GroundedClaim,
    ProjectDNA,
)


def project_dna_from_json(value: Any) -> ProjectDNA:
    """Convert a Snowflake VARIANT value into the immutable domain model."""
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        raise TypeError("Project DNA JSON must be an object")

    def claim(item: Any) -> GroundedClaim | None:
        if item is None:
            return None
        if not isinstance(item, dict):
            raise TypeError("Project DNA claim must be an object")
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            raise TypeError("Project DNA claim evidence must be an array")
        return GroundedClaim(
            value=str(item["value"]),
            confidence=ClaimConfidence(str(item["confidence"])),
            evidence=tuple(
                EvidenceReference(int(reference["section_sequence"]), str(reference["quote"]))
                for reference in evidence
            ),
        )

    def claims(field: str) -> tuple[GroundedClaim, ...]:
        items = raw.get(field, [])
        if not isinstance(items, list):
            raise TypeError(f"Project DNA {field} must be an array")
        mapped = tuple(claim(item) for item in items)
        if any(item is None for item in mapped):
            raise TypeError(f"Project DNA {field} cannot contain null claims")
        return tuple(item for item in mapped if item is not None)

    generated_at = raw["generated_at"]
    return ProjectDNA(
        dna_id=str(raw["dna_id"]),
        project_id=str(raw["project_id"]),
        document_id=str(raw["document_id"]),
        version=int(raw["version"]),
        project_name=claim(raw.get("project_name")),
        client_name=claim(raw.get("client_name")),
        industry=claim(raw.get("industry")),
        engagement_type=claim(raw.get("engagement_type")),
        summary=claim(raw.get("summary")),
        business_challenges=claims("business_challenges"),
        use_cases=claims("use_cases"),
        capabilities=claims("capabilities"),
        technologies=claims("technologies"),
        data_sources=claims("data_sources"),
        cloud_platforms=claims("cloud_platforms"),
        outcomes=claims("outcomes"),
        differentiators=claims("differentiators"),
        experts=claims("experts"),
        model=str(raw["model"]),
        prompt_version=str(raw["prompt_version"]),
        generated_at=(
            generated_at
            if isinstance(generated_at, datetime)
            else datetime.fromisoformat(str(generated_at))
        ),
    )
