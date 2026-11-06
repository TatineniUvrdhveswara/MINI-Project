from pathlib import Path

from app.memory.schemas import PaperChunk
from app.memory.store import ScientificMemoryStore
from app.retrieval.bm25 import bm25_scores
from app.retrieval.service import HybridRetrievalService


class FakeEmbeddings:
    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def _chunk(chunk_id: str, text: str) -> PaperChunk:
    return PaperChunk(
        chunk_id=chunk_id,
        paper_id="paper:1",
        text=text,
        page_start=2,
        page_end=2,
        source="test",
    )


def test_bm25_prioritizes_keyword_match() -> None:
    chunks = [_chunk("a", "retrieval systems use evidence"), _chunk("b", "unrelated biology experiment")]
    scores = bm25_scores("evidence retrieval", chunks)
    assert scores["a"] > scores.get("b", 0)


def test_hybrid_retrieval_merges_and_builds_citation_context(tmp_path: Path) -> None:
    store = ScientificMemoryStore(tmp_path / "metadata.db", tmp_path / "vectors")
    chunks = [
        _chunk("a", "retrieval systems use evidence"),
        _chunk("b", "evidence coverage improves citations"),
    ]
    store.upsert_paper({"paper_id": "paper:1", "title": "Test", "source": "test"}, "indexed")
    store.upsert_chunks(chunks, [[1.0, 0.0], [1.0, 0.0]])
    response = HybridRetrievalService(
        store, FakeEmbeddings(), dense_top_k=2, bm25_top_k=2, rerank_top_k=2, final_context_k=1
    ).retrieve("evidence retrieval")

    assert response.dense_candidates == 2
    assert response.bm25_candidates == 2
    assert response.merged_candidates == 2
    assert len(response.selected_evidence) == 1
    assert "Source: paper:1, page 2" in response.context
