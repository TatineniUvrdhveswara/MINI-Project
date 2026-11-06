from pydantic import BaseModel, Field

from ..memory.schemas import PaperChunk


class RetrievalCandidate(BaseModel):
    chunk: PaperChunk
    dense_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float
    retrieval_sources: list[str] = Field(default_factory=list)


class RetrievalResponse(BaseModel):
    query: str
    dense_candidates: int
    bm25_candidates: int
    merged_candidates: int
    selected_evidence: list[RetrievalCandidate]
    context: str
