import re

from .schemas import PaperChunk
from ..mcp.schemas import PaperRecord


def chunk_pages(
    paper: PaperRecord,
    pages: list[tuple[int, str]],
    chunk_size: int = 1200,
    overlap: int = 180,
) -> list[PaperChunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: list[PaperChunk] = []
    for page_number, text in pages:
        words = re.findall(r"\S+", text)
        start = 0
        sequence = 0
        while start < len(words):
            selected = words[start : start + chunk_size]
            if not selected:
                break
            chunks.append(
                PaperChunk(
                    chunk_id=f"{paper.paper_id}:p{page_number}:c{sequence:04d}",
                    paper_id=paper.paper_id,
                    text=" ".join(selected),
                    section="Document",
                    page_start=page_number,
                    page_end=page_number,
                    year=paper.year,
                    source=paper.source,
                )
            )
            sequence += 1
            if start + chunk_size >= len(words):
                break
            start += chunk_size - overlap
    return chunks
