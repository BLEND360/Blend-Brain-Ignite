"""Scoped retrieval and grounded answer workflow tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blend_brain.knowledge_retrieval.application import (
    HybridRetrievalService,
    QuestionAnsweringService,
)
from blend_brain.knowledge_retrieval.domain import (
    GeneratedAnswerDraft,
    GeneratedCitationDraft,
    GeneratedClaimDraft,
    IndexedSection,
    InvalidRetrievalRequestError,
    RetrievalHit,
    RetrievalScope,
    UngroundedAnswerError,
)
from blend_brain.knowledge_retrieval.infrastructure import FaissHybridSearchIndexFactory
from tests.unit.knowledge_retrieval.helpers import hit, section

if TYPE_CHECKING:
    from blend_brain.knowledge_retrieval.application.ports import HybridSearchIndex


class CorpusRepository:
    """In-memory scoped corpus test double."""

    def __init__(self) -> None:
        self.calls = 0

    def load(self, scope: RetrievalScope) -> tuple[IndexedSection, ...]:
        self.calls += 1
        assert scope.project_ids
        return (section(project_id=scope.project_ids[0]),)


class Embeddings:
    """Deterministic query embedding test double."""

    def embed_query(self, query: str) -> tuple[float, ...]:
        assert query
        return (1.0, 0.0, 0.0)


class IndexFactory:
    """Bridge the helper's deliberately narrow repository type."""

    def __init__(self) -> None:
        self.factory = FaissHybridSearchIndexFactory()

    def build(self, sections: tuple[IndexedSection, ...]) -> HybridSearchIndex:
        return self.factory.build(sections)


class Retriever:
    """Configurable retriever test double."""

    def __init__(self, hits: tuple[RetrievalHit, ...]) -> None:
        self.hits = hits
        self.limit: int | None = None

    def retrieve(
        self, question: str, scope: RetrievalScope, *, limit: int
    ) -> tuple[RetrievalHit, ...]:
        assert question
        assert scope.project_ids
        self.limit = limit
        return self.hits


class Generator:
    """Configurable answer generator test double."""

    def __init__(self, draft: GeneratedAnswerDraft) -> None:
        self.draft = draft
        self.called = False

    def generate(self, question: str, evidence: tuple[RetrievalHit, ...]) -> GeneratedAnswerDraft:
        assert question
        assert evidence
        self.called = True
        return self.draft


def draft(
    *, source_id: str = "S1", quote: str = "reduced planning time by 30%"
) -> GeneratedAnswerDraft:
    """Return one answerable model draft."""
    return GeneratedAnswerDraft(
        answerable=True,
        claims=(
            GeneratedClaimDraft(
                "The project reduced planning time by 30%.",
                (GeneratedCitationDraft(source_id, quote),),
            ),
        ),
    )


def test_retrieval_cache_refresh_invalidation_and_scope_isolation() -> None:
    repository = CorpusRepository()
    service = HybridRetrievalService(
        corpus_repository=repository,
        embedding_gateway=Embeddings(),
        index_factory=IndexFactory(),
        max_cached_scopes=1,
    )
    first = RetrievalScope(("project-1",))
    second = RetrievalScope(("project-2",))

    assert service.retrieve("Snowflake", first, limit=1)
    assert service.retrieve("Snowflake", first, limit=1)
    assert repository.calls == 1
    service.retrieve("Snowflake", second, limit=1)
    service.retrieve("Snowflake", first, limit=1)
    assert repository.calls == 3
    assert service.refresh(first) == 1
    assert service.invalidate(first) is True
    assert service.invalidate(first) is False


@pytest.mark.parametrize("question", ["", "   "])
def test_retrieval_rejects_empty_questions(question: str) -> None:
    service = HybridRetrievalService(
        corpus_repository=CorpusRepository(),
        embedding_gateway=Embeddings(),
        index_factory=IndexFactory(),
    )
    with pytest.raises(InvalidRetrievalRequestError):
        service.retrieve(question, RetrievalScope(("p",)), limit=1)
    with pytest.raises(InvalidRetrievalRequestError, match="limit"):
        service.retrieve("valid", RetrievalScope(("p",)), limit=0)


def test_question_answering_validates_citations_and_computes_confidence() -> None:
    retriever = Retriever((hit(),))
    service = QuestionAnsweringService(retriever=retriever, answer_generator=Generator(draft()))

    answer = service.ask("What improved?", RetrievalScope(("project-1",)))

    assert answer.answerable is True
    assert answer.answer == "The project reduced planning time by 30%."
    assert answer.claims[0].citation_ids == ("C1",)
    assert answer.citations[0].heading == "Outcome"
    assert 0.0 < answer.confidence.score <= 0.95
    assert answer.confidence.breakdown.citation_coverage == 1.0
    assert retriever.limit == 8
    with pytest.raises(InvalidRetrievalRequestError, match="top_k"):
        service.ask("What improved?", RetrievalScope(("project-1",)), top_k=0)


def test_question_answering_returns_explicit_insufficient_evidence_states() -> None:
    generator = Generator(draft())
    no_hits = QuestionAnsweringService(retriever=Retriever(()), answer_generator=generator)
    answer = no_hits.ask("Unknown?", RetrievalScope(("p",)))
    assert answer.answerable is False
    assert answer.confidence.score == 0.0
    assert generator.called is False

    abstaining = Generator(GeneratedAnswerDraft(answerable=False, claims=(), reason="Not stated."))
    answer = QuestionAnsweringService(
        retriever=Retriever((hit(),)), answer_generator=abstaining
    ).ask("Unknown?", RetrievalScope(("p",)))
    assert answer.reason == "Not stated."


@pytest.mark.parametrize(
    "invalid",
    [
        draft(source_id="S9"),
        draft(quote="invented outcome"),
        GeneratedAnswerDraft(answerable=True, claims=()),
        GeneratedAnswerDraft(answerable=False, claims=(GeneratedClaimDraft("bad", ()),)),
        GeneratedAnswerDraft(
            answerable=True,
            claims=(GeneratedClaimDraft("", (GeneratedCitationDraft("S1", "Snowflake"),)),),
        ),
    ],
)
def test_question_answering_rejects_ungrounded_drafts(invalid: GeneratedAnswerDraft) -> None:
    service = QuestionAnsweringService(
        retriever=Retriever((hit(),)), answer_generator=Generator(invalid)
    )
    with pytest.raises(UngroundedAnswerError):
        service.ask("Question?", RetrievalScope(("p",)))
