from datetime import datetime, timezone

from ..schemas import ResearchSession
from .schemas import ResearchReport


def build_report(session: ResearchSession) -> ResearchReport:
    answer = session.answer.answer if session.answer else "No generated answer is available."
    evidence = [
        f"{candidate.chunk.text} (paper {candidate.chunk.paper_id}, page {candidate.chunk.page_start or 'unknown'})"
        for candidate in (session.retrieval.selected_evidence if session.retrieval else [])
    ]
    limitations = []
    if not session.retrieval or not session.retrieval.selected_evidence:
        limitations.append("No retrieved evidence was available.")
    if session.evaluation and session.evaluation.warnings:
        limitations.extend(session.evaluation.warnings)
    if session.answer and session.answer.provider == "grounded_fallback":
        limitations.append("A deterministic fallback generator was used; human review is required.")
    references = [
        {"citation_id": citation.citation_id, "title": citation.title, "source": citation.source, "year": citation.year}
        for citation in session.citations
    ]
    return ResearchReport(
        session_id=str(session.session_id),
        title=f"Research report: {session.query}",
        executive_summary=(
            f"Answer generated from {len(evidence)} selected evidence chunk(s) and "
            f"{len(references)} citation record(s)."
        ),
        answer=answer,
        evidence_summary=evidence,
        limitations=limitations,
        references=references,
        evaluation_score=session.evaluation.overall_score if session.evaluation else None,
        generated_at=datetime.now(timezone.utc),
    )


def render_markdown(report: ResearchReport) -> str:
    references = "\n".join(
        f"- **{item['citation_id']}** — {item['title']} ({item['source']}, {item['year'] or 'year unavailable'})"
        for item in report.references
    ) or "- No references available."
    evidence = "\n".join(f"- {item}" for item in report.evidence_summary) or "- No evidence selected."
    limitations = "\n".join(f"- {item}" for item in report.limitations) or "- None recorded."
    score = f"{report.evaluation_score:.2f}" if report.evaluation_score is not None else "not evaluated"
    return (
        f"# {report.title}\n\n"
        f"## Executive summary\n\n{report.executive_summary}\n\n"
        f"## Answer\n\n{report.answer}\n\n"
        f"## Evidence\n\n{evidence}\n\n"
        f"## Evaluation score\n\n{score}\n\n"
        f"## Limitations\n\n{limitations}\n\n"
        f"## References\n\n{references}\n"
    )
