from app.generation.evaluator import evaluate_answer
from app.generation.provider import GroundedFallbackProvider
from app.retrieval.schemas import RetrievalCandidate, RetrievalResponse
from app.memory.schemas import PaperChunk


def _retrieval() -> RetrievalResponse:
    chunk = PaperChunk(
        chunk_id="paper:1:p1:c1",
        paper_id="paper:1",
        text="Dense retrieval improves evidence coverage for scientific questions.",
        page_start=1,
        source="test",
    )
    return RetrievalResponse(
        query="evidence coverage",
        dense_candidates=1,
        bm25_candidates=1,
        merged_candidates=1,
        selected_evidence=[
            RetrievalCandidate(
                chunk=chunk,
                dense_score=0.9,
                bm25_score=1.0,
                rerank_score=0.9,
                retrieval_sources=["dense", "bm25"],
            )
        ],
        context="[1] Dense retrieval improves evidence coverage for scientific questions.",
    )


def test_fallback_generation_is_grounded_and_cited() -> None:
    retrieval = _retrieval()
    answer = GroundedFallbackProvider().generate("How does evidence coverage improve?", retrieval)
    evaluation = evaluate_answer("How does evidence coverage improve?", answer, retrieval)

    assert answer.grounded is True
    assert answer.citation_ids == ["paper:1:p1:c1"]
    assert "[E1]" in answer.answer
    assert evaluation.citation_support == 1
    assert evaluation.unsupported_claims == 0


def test_empty_evidence_is_explicitly_evaluated_as_failed() -> None:
    retrieval = RetrievalResponse(
        query="unknown",
        dense_candidates=0,
        bm25_candidates=0,
        merged_candidates=0,
        selected_evidence=[],
        context="",
    )
    answer = GroundedFallbackProvider().generate("unknown", retrieval)
    evaluation = evaluate_answer("unknown", answer, retrieval)

    assert "Insufficient evidence" in answer.answer
    assert evaluation.passed is False
    assert evaluation.warnings
