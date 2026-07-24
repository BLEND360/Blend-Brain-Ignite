"""Persisted Project DNA deserialization tests."""

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, cast

import pytest

from blend_brain.knowledge_enrichment.infrastructure.project_dna_mapper import (
    project_dna_from_json,
)
from tests.unit.knowledge_enrichment.helpers import dna


def test_maps_persisted_dna_object() -> None:
    mapped = project_dna_from_json(_persisted())

    assert mapped == dna()
    assert mapped.technologies[0].value == "Snowflake"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda _value: [], "must be an object"),
        (lambda value: {**value, "project_name": []}, "claim must be an object"),
        (
            lambda value: {**value, "project_name": {"value": "x", "confidence": "high"}},
            "evidence must be an array",
        ),
        (lambda value: {**value, "technologies": None}, "must be an array"),
        (lambda value: {**value, "technologies": [None]}, "cannot contain null"),
    ],
)
def test_rejects_corrupt_persisted_shapes(
    mutation: Callable[[dict[str, Any]], Any], message: str
) -> None:
    raw = _persisted()
    transformed = mutation(raw)

    with pytest.raises(TypeError, match=message):
        project_dna_from_json(transformed)


def _persisted() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(json.dumps(asdict(dna()), default=str)))
