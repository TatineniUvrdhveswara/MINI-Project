import json
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .mcp.source_adapters import ArxivAdapter, SemanticScholarAdapter

settings = get_settings()
mcp = FastMCP("scientific-literature")
arxiv = ArxivAdapter(settings.request_timeout)
semantic_scholar = SemanticScholarAdapter(
    settings.request_timeout, settings.semantic_scholar_api_key
)


@mcp.tool()
def search_arxiv(query: str, limit: int = 10) -> dict[str, Any]:
    """Search arXiv and return normalized paper metadata."""
    return arxiv.search(query, limit).model_dump(mode="json")


@mcp.tool()
def search_semantic_scholar(query: str, limit: int = 10) -> dict[str, Any]:
    """Search Semantic Scholar and return normalized paper metadata."""
    return semantic_scholar.search(query, limit).model_dump(mode="json")


@mcp.tool()
def get_paper_metadata(identifier: str) -> dict[str, Any]:
    """Resolve a paper identifier into a normalized metadata record."""
    normalized = identifier.strip()
    if normalized.startswith("arxiv:"):
        result = arxiv.search(normalized.removeprefix("arxiv:"), 1)
    else:
        result = semantic_scholar.search(normalized, 1)
    paper = result.papers[0] if result.papers else None
    return {"paper": paper.model_dump(mode="json") if paper else None, "error": result.error}


@mcp.tool()
def download_paper_pdf(pdf_url: str) -> dict[str, Any]:
    """Download an accessible PDF and return its bytes as base64 for persistence."""
    import base64
    import urllib.request

    try:
        request = urllib.request.Request(
            pdf_url, headers={"User-Agent": "ScientificResearchAssistant/0.1"}
        )
        with urllib.request.urlopen(request, timeout=settings.request_timeout) as response:
            content = response.read()
        return {"content_base64": base64.b64encode(content).decode("ascii"), "error": None}
    except (OSError, ValueError) as exc:
        return {"content_base64": None, "error": str(exc)}


if __name__ == "__main__":
    print("Starting scientific-literature MCP server", file=sys.stderr)
    mcp.run(transport="stdio")
