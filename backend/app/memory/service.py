from pathlib import Path

from ..mcp.schemas import PaperRecord
from .chunker import chunk_pages
from .embeddings import EmbeddingProvider
from .extractor import extract_pdf_pages
from .schemas import IngestionResult, MemorySearchResult, MemoryStats
from .store import ScientificMemoryStore


class MemoryService:
    def __init__(
        self,
        store: ScientificMemoryStore,
        embeddings: EmbeddingProvider,
        chunk_size: int = 1200,
        overlap: int = 180,
    ) -> None:
        self.store = store
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.overlap = overlap

    def ingest(self, paper: PaperRecord, pdf_path: Path | None) -> IngestionResult:
        self.store.upsert_paper(paper.model_dump(mode="json"), "processing")
        if pdf_path is None:
            self.store.mark_paper_status(paper.paper_id, "metadata_only")
            return IngestionResult(
                paper_id=paper.paper_id,
                status="metadata_only",
                chunks_created=0,
                chunks_embedded=0,
                detail="No accessible PDF was available.",
            )
        try:
            pages = extract_pdf_pages(pdf_path)
            chunks = chunk_pages(paper, pages, self.chunk_size, self.overlap)
            vectors = self.embeddings.encode([chunk.text for chunk in chunks])
            self.store.upsert_chunks(chunks, vectors)
            self.store.mark_paper_status(paper.paper_id, "indexed")
            return IngestionResult(
                paper_id=paper.paper_id,
                status="indexed",
                chunks_created=len(chunks),
                chunks_embedded=len(vectors),
                detail="PDF extracted, chunked, embedded, and persisted.",
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self.store.mark_paper_status(paper.paper_id, "failed")
            return IngestionResult(
                paper_id=paper.paper_id,
                status="failed",
                chunks_created=0,
                chunks_embedded=0,
                detail=str(exc),
            )

    def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]:
        vectors = self.embeddings.encode([query])
        return self.store.search(vectors[0], limit) if vectors else []

    def stats(self) -> MemoryStats:
        return self.store.stats()
