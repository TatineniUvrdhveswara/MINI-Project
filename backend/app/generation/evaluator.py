import re

from ..retrieval.schemas import RetrievalResponse
from .schemas import EvaluationResult, GeneratedAnswer


def evaluate_answer(
    query: str, answer: GeneratedAnswer, retrieval: RetrievalResponse
) -> EvaluationResult:
    evidence = retrieval.selected_evidence
    warnings: list[str] = []
    answer_terms = set(_terms(answer.answer))
    query_terms = set(_terms(query))
    evidence_terms = set(_terms(retrieval.context))
    relevance = len(query_terms & answer_terms) / max(len(query_terms), 1)
    coverage = len(answer_terms & evidence_terms) / max(len(answer_terms), 1)
    expected_ids = {candidate.chunk.chunk_id for candidate in evidence}
    cited_ids = set(answer.citation_ids)
    citation_support = len(cited_ids & expected_ids) / max(len(cited_ids), 1)
    unsupported = max(0, len(cited_ids - expected_ids))
    if not evidence:
        warnings.append("No retrieved evidence was available.")
    if not answer.citation_ids and evidence:
        warnings.append("The answer does not include evidence citations.")
    if unsupported:
        warnings.append("One or more answer citations do not match selected evidence.")
    consistency = coverage if answer.grounded else 0.0
    completeness = min(1.0, len(evidence) / 3) if evidence else 0.0
    overall = (relevance + coverage + citation_support + consistency + completeness) / 5
    return EvaluationResult(
        relevance=min(1.0, relevance),
        evidence_coverage=min(1.0, coverage),
        citation_support=min(1.0, citation_support),
        factual_consistency=min(1.0, consistency),
        completeness=completeness,
        overall_score=overall,
        supported_claims=len(cited_ids & expected_ids),
        unsupported_claims=unsupported,
        warnings=warnings,
        passed=overall >= 0.5 and unsupported == 0 and bool(evidence),
    )


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
