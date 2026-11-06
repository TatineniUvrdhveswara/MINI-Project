from pydantic import BaseModel, Field


class PaperChunk(BaseModel):
    chunk_id: str
    paper_id: str
    text: str = Field(min_length=1)
    section: str = "Document"
    page_start: int | None = None
    page_end: int | None = None
    year: int | None = None
    source: str


class MemoryStats(BaseModel):
    papers: int
    chunks: int
    embedded_chunks: int
    storage: str
    embedding_model: str


class IngestionResult(BaseModel):
    paper_id: str
    status: str
    chunks_created: int
    chunks_embedded: int
    detail: str


class MemorySearchResult(BaseModel):
    chunk: PaperChunk
    distance: float | None = None
