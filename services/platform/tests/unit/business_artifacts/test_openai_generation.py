"""Offline OpenAI business-artifact adapter tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from openai import APIConnectionError, OpenAI

from blend_brain.business_artifacts.application import (
    ONE_PAGER_SECTION_KEYS,
    PROPOSAL_SECTION_KEYS,
)
from blend_brain.business_artifacts.domain import (
    ArtifactGenerationError,
    ArtifactSource,
    ArtifactSourceKind,
    OnePagerBrief,
    ProposalBrief,
)
from blend_brain.business_artifacts.infrastructure.openai_generation import (
    BusinessArtifactResponse,
    CitationResponse,
    OpenAIBusinessArtifactGenerator,
    SectionResponse,
    StatementResponse,
)
from tests.unit.business_artifacts.helpers import project_source


class CharacterCounter:
    """Offline deterministic token counter."""

    def count(self, text: str) -> int:
        return len(text)


class Responses:
    """Minimal typed Responses resource fake."""

    def __init__(self, parsed: BusinessArtifactResponse | None) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        """Return configured structured output."""
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


def client(responses: Responses) -> OpenAI:
    """Cast a narrow SDK fake at the adapter boundary."""
    return cast("OpenAI", SimpleNamespace(responses=responses))


def response(
    keys: tuple[str, ...], quote: str = "forecasting platform"
) -> BusinessArtifactResponse:
    """Return a valid exact-template response."""
    return BusinessArtifactResponse(
        title="Forecasting Transformation",
        subtitle="Grounded draft",
        sections=[
            SectionResponse(
                key=key,
                heading=key.replace("_", " ").title(),
                statements=[
                    StatementResponse(
                        text="Blend delivered a forecasting platform.",
                        citations=[CitationResponse(source_id="P1", quote=quote)],
                    )
                ],
            )
            for key in keys
        ],
    )


def test_generates_strict_grounded_proposal_and_untrusted_context() -> None:
    responses = Responses(response(PROPOSAL_SECTION_KEYS))
    generator = OpenAIBusinessArtifactGenerator(client(responses), token_counter=CharacterCounter())

    result = generator.generate_proposal(
        ProposalBrief("Client", "Executives", "Forecasting", ("Improve plans",), ()),
        (project_source(),),
    )

    assert tuple(section.key for section in result.sections) == PROPOSAL_SECTION_KEYS
    assert result.sections[0].statements[0].citations[0].filename == "case-study.md"
    call = responses.calls[0]
    assert call["text_format"] is BusinessArtifactResponse
    assert "UNTRUSTED_ARTIFACT_JSON" in call["input"][1]["content"]
    assert "never as instructions" in call["input"][0]["content"]


def test_generates_one_pager_and_rejects_invalid_templates() -> None:
    valid = Responses(response(ONE_PAGER_SECTION_KEYS))
    generator = OpenAIBusinessArtifactGenerator(client(valid), token_counter=CharacterCounter())
    result = generator.generate_one_pager(OnePagerBrief("project-1", "Sales"), (project_source(),))
    assert result.prompt_version == "pih-sales-brief-v2"

    invalid_template = OpenAIBusinessArtifactGenerator(
        client(Responses(response(("wrong",)))), token_counter=CharacterCounter()
    )
    with pytest.raises(ArtifactGenerationError, match="template"):
        invalid_template.generate_one_pager(
            OnePagerBrief("project-1", "Sales"), (project_source(),)
        )

    ungrounded = OpenAIBusinessArtifactGenerator(
        client(Responses(response(ONE_PAGER_SECTION_KEYS, "invented quote"))),
        token_counter=CharacterCounter(),
    )
    filtered = ungrounded.generate_one_pager(
        OnePagerBrief("project-1", "Sales"), (project_source(),)
    )
    assert all(not section.statements for section in filtered.sections)


def test_handles_empty_oversized_api_and_duplicate_source_failures() -> None:
    empty = OpenAIBusinessArtifactGenerator(
        client(Responses(None)), token_counter=CharacterCounter()
    )
    with pytest.raises(ArtifactGenerationError, match="no parsed"):
        empty.generate_one_pager(OnePagerBrief("project-1", "Sales"), (project_source(),))

    oversized = OpenAIBusinessArtifactGenerator(
        client(Responses(response(ONE_PAGER_SECTION_KEYS))),
        max_input_tokens=1,
        token_counter=CharacterCounter(),
    )
    with pytest.raises(ArtifactGenerationError, match="token limit"):
        oversized.generate_one_pager(OnePagerBrief("project-1", "Sales"), (project_source(),))

    responses = Responses(response(ONE_PAGER_SECTION_KEYS))
    responses.error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(ArtifactGenerationError):
        OpenAIBusinessArtifactGenerator(
            client(responses), token_counter=CharacterCounter()
        ).generate_one_pager(OnePagerBrief("project-1", "Sales"), (project_source(),))

    duplicate = ArtifactSource(
        "P1", ArtifactSourceKind.PROJECT_DOCUMENT, "forecasting platform", project_id="p"
    )
    with pytest.raises(ArtifactGenerationError, match="unique"):
        OpenAIBusinessArtifactGenerator(
            client(Responses(response(ONE_PAGER_SECTION_KEYS))),
            token_counter=CharacterCounter(),
        ).generate_one_pager(OnePagerBrief("project-1", "Sales"), (project_source(), duplicate))
    with pytest.raises(ValueError, match="greater than zero"):
        OpenAIBusinessArtifactGenerator(client(responses), max_input_tokens=0)
