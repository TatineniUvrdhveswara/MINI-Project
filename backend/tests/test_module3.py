from pathlib import Path

import pymupdf

from app.memory.chunker import chunk_pages
from app.memory.extractor import extract_pdf_pages
from app.memory.schemas import PaperChunk
from app.memory.service import MemoryService
from app.memory.store import ScientificMemoryStore
from app.mcp.schemas import PaperRecord


class FakeEmbeddings:
    model_name = "fake-test-model"

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]


def test_pdf_extraction_and_section_aware_chunking(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Introduction Evidence grounded retrieval improves research workflows.")
        document.save(pdf_path)

    paper = PaperRecord(paper_id="test:1", title="Test", source="test", year=2025)
    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(paper, pages, chunk_size=4, overlap=1)

    assert pages[0][0] == 1
    assert chunks
    assert chunks[0].paper_id == "test:1"
    assert chunks[0].page_start == 1


def test_memory_ingests_chunks_and_searches_persistently(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Persistent scientific memory stores searchable evidence chunks.")
        document.save(pdf_path)

    store = ScientificMemoryStore(tmp_path / "metadata.db", tmp_path / "vectors")
    service = MemoryService(store, FakeEmbeddings(), chunk_size=20, overlap=2)
    paper = PaperRecord(paper_id="test:2", title="Memory", source="test", year=2025)

    result = service.ingest(paper, pdf_path)
    matches = service.search("scientific memory")

    assert result.status == "indexed"
    assert result.chunks_created == result.chunks_embedded
    assert result.chunks_created > 0
    assert matches[0].chunk.paper_id == "test:2"
    assert service.stats().embedded_chunks == result.chunks_embedded
