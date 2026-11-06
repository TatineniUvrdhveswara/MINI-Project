import asyncio
from typing import Any

from .mcp.schemas import MCPTool, PaperRecord, SourceSearchResult
from .mcp_client import mcp_client
from .paper_store import paper_store


class MCPService:
    def discover_tools(self) -> list[MCPTool]:
        return asyncio.run(mcp_client.discover_tools())

    def search(self, query: str, sources: list[str], limit: int) -> list[SourceSearchResult]:
        return asyncio.run(mcp_client.search(query, sources, limit))

    def store_papers(self, papers: list[PaperRecord]) -> list[PaperRecord]:
        stored: list[PaperRecord] = []
        for paper in papers:
            try:
                stored.append(asyncio.run(mcp_client.download_and_store(paper)))
            except (OSError, ValueError, RuntimeError) as exc:
                paper_store.save_paper(paper)
                stored.append(paper.model_copy(update={"full_text_available": False}))
                print(f"Paper storage warning for {paper.paper_id}: {exc}")
        return stored

    @staticmethod
    def merge_unique(results: list[SourceSearchResult]) -> list[Any]:
        unique: dict[str, Any] = {}
        for result in results:
            for paper in result.papers:
                identity = paper.doi or paper.arxiv_id or paper.semantic_scholar_id or paper.paper_id
                unique[identity.lower()] = paper
        return list(unique.values())

