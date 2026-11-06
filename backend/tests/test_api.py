from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_endpoint_describes_components() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert {component["name"] for component in response.json()["components"]} >= {
        "api",
        "workflow-orchestrator",
    }


def test_query_creates_normalized_session() -> None:
    response = client.post(
        "/api/v1/research/query",
        json={
            "query": "  Compare   adaptive RAG methods and identify research gaps.  ",
            "filters": {"sources": [" arxiv ", "ARXIV"], "year_from": 2020},
        },
    )
    assert response.status_code == 201
    body = response.json()["session"]
    assert body["query"] == "Compare adaptive RAG methods and identify research gaps."
    assert body["filters"]["sources"] == ["arxiv"]


def test_query_rejects_short_input() -> None:
    response = client.post("/api/v1/research/query", json={"query": "short"})
    assert response.status_code == 422


def test_session_not_found() -> None:
    response = client.get("/api/v1/research/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
