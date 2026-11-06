import math
from collections import defaultdict

from ..memory.embeddings import EmbeddingProvider
from ..memory.schemas import MemorySearchResult, PaperChunk
from ..memory.store import ScientificMemoryStore
from .bm25 import bm25_scores, tokenize
from .schemas import RetrievalCandidate, RetrievalResponse


class HybridRetrievalService:
    def __init__(
        self,
        store: ScientificMemoryStore,
        embeddings: EmbeddingProvider,
        dense_top_k: int = 20,
        bm25_top_k: int = 20,
        rerank_top_k: int = 10,
        final_context_k: int = 5,
    ) -> None:
        self.store = store
        self.embeddings = embeddings
        self.dense_top_k = dense_top_k
        self.bm25_top_k = bm25_top_k
        self.rerank_top_k = rerank_top_k
        self.final_context_k = final_context_k

    def retrieve(self, query: str) -> RetrievalResponse:
        dense_results = self._dense(query)
        chunks = self.store.list_chunks()
        keyword_scores = bm25_scores(query, chunks)
        bm25_results = sorted(keyword_scores.items(), key=lambda item: item[1], reverse=True)[
            : self.bm25_top_k
        ]
        dense_scores = {
            result.chunk.chunk_id: _distance_to_score(result.distance)
            for result in dense_results
        }
        bm25_max = max((score for _, score in bm25_results), default=0.0)
        merged: dict[str, dict[str, object]] = defaultdict(dict)
        for result in dense_results:
            merged[result.chunk.chunk_id].update(
                chunk=result.chunk,
                dense_score=dense_scores[result.chunk.chunk_id],
            )
            merged[result.chunk.chunk_id].setdefault("sources", []).append("dense")
        for chunk_id, score in bm25_results:
            chunk = next(chunk for chunk in chunks if chunk.chunk_id == chunk_id)
            merged[chunk_id].update(chunk=chunk, bm25_score=score)
            merged[chunk_id].setdefault("sources", []).append("bm25")
        candidates = [
            RetrievalCandidate(
                chunk=item["chunk"],
                dense_score=item.get("dense_score"),
                bm25_score=item.get("bm25_score"),
                rerank_score=self._rerank(query, item["chunk"], item.get("dense_score"), item.get("bm25_score"), bm25_max),
                retrieval_sources=item["sources"],
            )
            for item in merged.values()
        ]
        candidates.sort(key=lambda candidate: candidate.rerank_score, reverse=True)
        selected = candidates[: self.rerank_top_k][: self.final_context_k]
        return RetrievalResponse(
            query=query,
            dense_candidates=len(dense_results),
            bm25_candidates=len(bm25_results),
            merged_candidates=len(candidates),
            selected_evidence=selected,
            context=self._build_context(selected),
        )

    def _dense(self, query: str) -> list[MemorySearchResult]:
        vectors = self.embeddings.encode([query])
        return self.store.search(vectors[0], self.dense_top_k) if vectors else []

    @staticmethod
    def _rerank(
        query: str,
        chunk: PaperChunk,
        dense_score: float | None,
        bm25_score: float | None,
        bm25_max: float,
    ) -> float:
        query_terms = set(tokenize(query))
        chunk_terms = set(tokenize(chunk.text))
        lexical_overlap = len(query_terms & chunk_terms) / max(len(query_terms), 1)
        normalized_bm25 = (bm25_score or 0.0) / bm25_max if bm25_max else 0.0
        return 0.45 * (dense_score or 0.0) + 0.35 * normalized_bm25 + 0.20 * lexical_overlap

    @staticmethod
    def _build_context(candidates: list[RetrievalCandidate]) -> str:
        return "\n\n".join(
            f"[{index}] {candidate.chunk.text}\n"
            f"Source: {candidate.chunk.paper_id}, page {candidate.chunk.page_start or 'unknown'}"
            for index, candidate in enumerate(candidates, start=1)
        )


def _distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance))
