"""Question-answer orchestration and deterministic grounding enforcement."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blend_brain.knowledge_retrieval.domain import (
    AnswerCitation,
    AnswerConfidence,
    ConfidenceBand,
    ConfidenceBreakdown,
    GeneratedAnswerDraft,
    GroundedAnswer,
    GroundedAnswerClaim,
    InvalidRetrievalRequestError,
    RetrievalHit,
    RetrievalScope,
    UngroundedAnswerError,
)

if TYPE_CHECKING:
    from blend_brain.knowledge_retrieval.application.ports import AnswerGenerator, Retriever

_WHITESPACE = re.compile(r"\s+")


class QuestionAnsweringService:
    """Answer questions exclusively through validated retrieved claims."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        answer_generator: AnswerGenerator,
        default_top_k: int = 8,
        max_grounding_attempts: int = 2,
    ) -> None:
        if default_top_k <= 0 or not 1 <= max_grounding_attempts <= 3:
            raise ValueError("Question answering limits are invalid")
        self._retriever = retriever
        self._answer_generator = answer_generator
        self._default_top_k = default_top_k
        self._max_grounding_attempts = max_grounding_attempts

    def ask(
        self,
        question: str,
        scope: RetrievalScope,
        *,
        top_k: int | None = None,
    ) -> GroundedAnswer:
        """Retrieve, generate, validate, and score one grounded answer."""
        limit = self._default_top_k if top_k is None else top_k
        if limit <= 0:
            raise InvalidRetrievalRequestError("top_k must be greater than zero")
        hits = self._retriever.retrieve(question, scope, limit=limit)
        if not hits:
            return self._unanswerable(question, "No relevant evidence was found.")
        last_error: UngroundedAnswerError | None = None
        for _attempt in range(self._max_grounding_attempts):
            draft = self._answer_generator.generate(question.strip(), hits)
            try:
                return self._validated_answer(question, draft, hits)
            except UngroundedAnswerError as exception:
                last_error = exception
        if last_error is None:  # pragma: no cover - attempts are validated as positive
            raise RuntimeError("Grounding attempts were not executed")
        raise last_error

    def _validated_answer(
        self,
        question: str,
        draft: GeneratedAnswerDraft,
        hits: tuple[RetrievalHit, ...],
    ) -> GroundedAnswer:
        if not draft.answerable:
            if draft.claims:
                raise UngroundedAnswerError("An unanswerable draft cannot contain claims")
            return self._unanswerable(
                question,
                (draft.reason or "The retrieved evidence is insufficient.").strip(),
            )
        return self._ground(question, draft, hits)

    def _ground(
        self,
        question: str,
        draft: GeneratedAnswerDraft,
        hits: tuple[RetrievalHit, ...],
    ) -> GroundedAnswer:
        if not draft.claims:
            raise UngroundedAnswerError("An answerable draft requires at least one claim")
        sources = {hit.source_id: hit for hit in hits}
        citations: list[AnswerCitation] = []
        claims: list[GroundedAnswerClaim] = []
        citation_keys: dict[tuple[str, str], str] = {}
        cited_document_ids: set[str] = set()

        for claim in draft.claims:
            text = claim.text.strip()
            if not text or not claim.citations:
                raise UngroundedAnswerError("Every answer claim requires text and evidence")
            claim_citation_ids: list[str] = []
            for proposed in claim.citations:
                hit = sources.get(proposed.source_id)
                quote = proposed.quote.strip()
                if hit is None or not quote or quote not in hit.section.text:
                    raise UngroundedAnswerError(
                        "Answer evidence does not exist in the cited retrieval source",
                        source_id=proposed.source_id,
                    )
                key = (proposed.source_id, self._normalize(quote))
                citation_id = citation_keys.get(key)
                if citation_id is None:
                    citation_id = f"C{len(citations) + 1}"
                    section = hit.section
                    citations.append(
                        AnswerCitation(
                            citation_id=citation_id,
                            project_id=section.project_id,
                            document_id=section.document_id,
                            filename=section.filename,
                            section_sequence=section.sequence,
                            quote=quote,
                            page_number=section.page_number,
                            slide_number=section.slide_number,
                            heading=section.heading,
                        )
                    )
                    citation_keys[key] = citation_id
                if citation_id not in claim_citation_ids:
                    claim_citation_ids.append(citation_id)
                cited_document_ids.add(hit.section.document_id)
            claims.append(GroundedAnswerClaim(text=text, citation_ids=tuple(claim_citation_ids)))

        confidence = self._confidence(hits, len(claims), len(cited_document_ids))
        return GroundedAnswer(
            question=question.strip(),
            answerable=True,
            answer=" ".join(claim.text for claim in claims),
            claims=tuple(claims),
            citations=tuple(citations),
            confidence=confidence,
        )

    @staticmethod
    def _confidence(
        hits: tuple[RetrievalHit, ...], claim_count: int, cited_document_count: int
    ) -> AnswerConfidence:
        top = hits[0]
        dense = 0.0 if top.dense_score is None else _clamp((top.dense_score + 1.0) / 2.0)
        lexical = (
            0.0
            if top.lexical_score is None
            else _clamp(top.lexical_score / (top.lexical_score + 3.0))
        )
        if top.dense_score is None:
            retrieval_strength = lexical
        elif top.lexical_score is None:
            retrieval_strength = dense
        else:
            retrieval_strength = 0.6 * dense + 0.4 * lexical
        citation_coverage = 1.0
        diversity_target = min(2, claim_count)
        source_diversity = _clamp(cited_document_count / diversity_target)
        score = min(
            0.95,
            _clamp(0.55 * retrieval_strength + 0.30 * citation_coverage + 0.15 * source_diversity),
        )
        band = (
            ConfidenceBand.HIGH
            if score >= 0.8
            else ConfidenceBand.MEDIUM
            if score >= 0.55
            else ConfidenceBand.LOW
        )
        return AnswerConfidence(
            score=round(score, 4),
            band=band,
            breakdown=ConfidenceBreakdown(
                retrieval_strength=round(retrieval_strength, 4),
                citation_coverage=citation_coverage,
                source_diversity=round(source_diversity, 4),
            ),
        )

    @staticmethod
    def _unanswerable(question: str, reason: str) -> GroundedAnswer:
        return GroundedAnswer(
            question=question.strip(),
            answerable=False,
            answer=None,
            claims=(),
            citations=(),
            confidence=AnswerConfidence(
                score=0.0,
                band=ConfidenceBand.LOW,
                breakdown=ConfidenceBreakdown(0.0, 0.0, 0.0),
            ),
            reason=reason,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return _WHITESPACE.sub(" ", value).strip().casefold()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
