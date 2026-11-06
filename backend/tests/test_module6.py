from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, workflow_traces
from app.schemas import ResearchSession, QueryFilters
from app.workflow.report import build_report, render_markdown

client = TestClient(app)


def test_report_builder_renders_structured_markdown() -> None:
    session = ResearchSession(
        query="Compare retrieval approaches",
        filters=QueryFilters(),
    )
    report = build_report(session)
    markdown = render_markdown(report)
    assert report.title.startswith("Research report:")
    assert "## Executive summary" in markdown
    assert "## Limitations" in markdown


def test_report_requires_no_llm_and_updates_session() -> None:
    created = client.post(
        "/api/v1/research/query",
        json={"query": "Compare report generation workflows."},
    ).json()["session"]
    response = client.post(
        f"/api/v1/research/sessions/{created['session_id']}/report"
    )
    assert response.status_code == 200
    assert response.json()["session"]["current_stage"] == "report_built"
    assert "# Research report:" in response.json()["report"]["markdown"]


def test_refinement_cycle_is_bounded() -> None:
    created = client.post(
        "/api/v1/research/query",
        json={"query": "Evaluate bounded refinement workflows."},
    ).json()["session"]
    session_id = created["session_id"]
    for _ in range(3):
        response = client.post(
            f"/api/v1/research/sessions/{session_id}/final-decision",
            json={"evaluation_sufficient": False},
        )
    assert response.status_code == 200
    assert response.json()["current_stage"] == "refinement_limit_reached"
    assert response.json()["refinement_cycles"] == 2
