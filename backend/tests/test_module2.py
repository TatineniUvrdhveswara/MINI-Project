from fastapi.testclient import TestClient

from app.main import app, mcp_service
from app.memory.schemas import MemoryStats
from app.mcp.schemas import PaperRecord, SourceSearchResult

client = TestClient(app)


def test_query_creates_initial_provisional_jev_decision(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.scientific_memory.stats",
        lambda: MemoryStats(
            papers=0,
            chunks=0,
            embedded_chunks=0,
            storage="test",
            embedding_model="test",
        ),
    )
    response = client.post(
        "/api/v1/research/query",
        json={"query": "Find recent methods for grounded scientific research."},
    )
    assert response.status_code == 201
    session = response.json()["session"]
    assert session["initial_jev"]["action"] == "acquire"
    assert session["initial_jev"]["implementation"] == "provisional-memory-adequacy-policy"


def test_mcp_tools_are_discoverable() -> None:
    response = client.get("/api/v1/mcp/tools")
    assert response.status_code == 200
    assert {tool["name"] for tool in response.json()["tools"]} == {
        "search_arxiv",
        "search_semantic_scholar",
        "get_paper_metadata",
        "download_paper_pdf",
    }


def test_search_normalizes_and_deduplicates_results(monkeypatch) -> None:
    paper = PaperRecord(
        paper_id="arxiv:123",
        title="Evidence grounded retrieval",
        source="arxiv",
        arxiv_id="123",
        year=2025,
        paper_url="https://arxiv.org/abs/123",
    )
    results = [
        SourceSearchResult(source="arxiv", papers=[paper], duration_ms=2),
        SourceSearchResult(source="semantic_scholar", papers=[paper], duration_ms=3),
    ]
    monkeypatch.setattr(mcp_service, "search", lambda query, sources, limit: results)

    created = client.post(
        "/api/v1/research/query",
        json={"query": "Find evidence grounded retrieval methods."},
    ).json()["session"]
    response = client.post(
        f"/api/v1/research/sessions/{created['session_id']}/literature",
        json={"limit": 5},
    )

    assert response.status_code == 200
    session = response.json()["session"]
    assert len(session["papers"]) == 1
    assert session["citations"][0]["citation_id"] == "arxiv:123"


def test_final_jev_refines_when_evidence_is_not_sufficient(monkeypatch) -> None:
    monkeypatch.setattr(mcp_service, "search", lambda query, sources, limit: [])
    created = client.post(
        "/api/v1/research/query",
        json={"query": "Compare scientific retrieval evaluation methods."},
    ).json()["session"]
    client.post(f"/api/v1/research/sessions/{created['session_id']}/literature", json={})
    response = client.post(
        f"/api/v1/research/sessions/{created['session_id']}/final-decision",
        json={"evaluation_sufficient": False},
    )

    assert response.status_code == 200
    assert response.json()["final_jev"]["action"] == "stop_insufficient_evidence"
