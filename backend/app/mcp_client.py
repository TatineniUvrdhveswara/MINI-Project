import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import get_settings
from .mcp.schemas import MCPTool, PaperRecord, SourceSearchResult
from .paper_store import paper_store


class MCPClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.server = StdioServerParameters(
            command=settings.mcp_server_command,
            args=["-m", settings.mcp_server_script.removesuffix(".py").replace("\\", ".").replace("/", ".")],
            env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        )

    async def discover_tools(self) -> list[MCPTool]:
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self.server))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.list_tools()
            return [
                MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema,
                    source="scientific-literature-mcp",
                )
                for tool in result.tools
            ]

    async def search(self, query: str, sources: list[str], limit: int) -> list[SourceSearchResult]:
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self.server))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            selected = set(sources) or {"arxiv", "semantic_scholar"}
            results: list[SourceSearchResult] = []
            for source, tool_name in (
                ("arxiv", "search_arxiv"),
                ("semantic_scholar", "search_semantic_scholar"),
            ):
                if source not in selected:
                    continue
                result = await session.call_tool(
                    tool_name, arguments={"query": query, "limit": limit}
                )
                results.append(SourceSearchResult.model_validate(_tool_payload(result)))
            return results

    async def download_and_store(self, paper: PaperRecord) -> PaperRecord:
        if not paper.pdf_url:
            return paper_store.save_paper(paper)
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self.server))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.call_tool(
                "download_paper_pdf", arguments={"pdf_url": paper.pdf_url}
            )
            payload = _tool_payload(result)
        import base64

        encoded = payload.get("content_base64")
        pdf_bytes = base64.b64decode(encoded) if encoded else None
        return paper_store.save_paper(paper, pdf_bytes)


def _tool_payload(result: Any) -> dict[str, Any]:
    if not result.content or not hasattr(result.content[0], "text"):
        raise ValueError("MCP tool returned no JSON content")
    return json.loads(result.content[0].text)


mcp_client = MCPClient()
