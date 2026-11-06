import re
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

from .schemas import PaperRecord, SourceSearchResult

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _year(value: str | None) -> int | None:
    return int(value[:4]) if value and value[:4].isdigit() else None


def _request_json(url: str, headers: Mapping[str, str], timeout: float) -> Any:
    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class ArxivAdapter:
    source = "arxiv"
    tool = "search_arxiv"

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def search(self, query: str, limit: int = 10) -> SourceSearchResult:
        started = time.perf_counter()
        try:
            params = urllib.parse.urlencode(
                {"search_query": f"all:{query}", "start": 0, "max_results": min(limit, 50)}
            )
            raw = _request_json(
                f"https://export.arxiv.org/api/query?{params}",
                {"User-Agent": "ScientificResearchAssistant/0.1"},
                self.timeout,
            )
            root = ET.fromstring(raw)
            papers: list[PaperRecord] = []
            for entry in root.findall("atom:entry", ARXIV_NS):
                entry_id = _clean(entry.findtext("atom:id", namespaces=ARXIV_NS))
                if not entry_id:
                    continue
                arxiv_id = entry_id.rsplit("/", 1)[-1]
                authors = [
                    author.text.strip()
                    for author in entry.findall("atom:author/atom:name", ARXIV_NS)
                    if author.text and author.text.strip()
                ]
                pdf_url = next(
                    (
                        link.attrib.get("href")
                        for link in entry.findall("atom:link", ARXIV_NS)
                        if link.attrib.get("title") == "pdf"
                    ),
                    None,
                )
                papers.append(
                    PaperRecord(
                        paper_id=f"arxiv:{arxiv_id}",
                        title=_clean(entry.findtext("atom:title", namespaces=ARXIV_NS)) or "Untitled paper",
                        authors=authors,
                        abstract=_clean(entry.findtext("atom:summary", namespaces=ARXIV_NS)),
                        year=_year(entry.findtext("atom:published", namespaces=ARXIV_NS)),
                        arxiv_id=arxiv_id,
                        source=self.source,
                        paper_url=entry_id,
                        pdf_url=pdf_url,
                        full_text_available=pdf_url is not None,
                    )
                )
            return SourceSearchResult(source=self.source, papers=papers, duration_ms=_elapsed_ms(started))
        except (ET.ParseError, OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            return _failed_result(self.source, started, str(exc))


class SemanticScholarAdapter:
    source = "semantic_scholar"
    tool = "search_semantic_scholar"

    def __init__(self, timeout: float = 15.0, api_key: str | None = None) -> None:
        self.timeout = timeout
        self.api_key = api_key

    def search(self, query: str, limit: int = 10) -> SourceSearchResult:
        started = time.perf_counter()
        try:
            params = urllib.parse.urlencode(
                {
                    "query": query,
                    "limit": min(limit, 100),
                    "fields": "paperId,title,authors,abstract,year,externalIds,url,openAccessPdf",
                }
            )
            headers = {"User-Agent": "ScientificResearchAssistant/0.1"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            data = _request_json(
                f"https://api.semanticscholar.org/graph/v1/paper/search?{params}",
                headers,
                self.timeout,
            )
            payload = json.loads(data)
            papers = [self._normalize(item) for item in payload.get("data", []) if item.get("paperId")]
            return SourceSearchResult(
                source=self.source, papers=papers, duration_ms=_elapsed_ms(started)
            )
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, TypeError) as exc:
            return _failed_result(self.source, started, str(exc))

    def _normalize(self, item: dict[str, Any]) -> PaperRecord:
        external_ids = item.get("externalIds") or {}
        open_access = item.get("openAccessPdf") or {}
        return PaperRecord(
            paper_id=f"semantic-scholar:{item['paperId']}",
            title=_clean(item.get("title")) or "Untitled paper",
            authors=[
                author["name"]
                for author in item.get("authors") or []
                if isinstance(author, dict) and author.get("name")
            ],
            abstract=_clean(item.get("abstract")),
            year=item.get("year"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            semantic_scholar_id=item["paperId"],
            source=self.source,
            paper_url=item.get("url"),
            pdf_url=open_access.get("url"),
            full_text_available=bool(open_access.get("url")),
        )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _failed_result(source: str, started: float, error: str) -> SourceSearchResult:
    return SourceSearchResult(source=source, duration_ms=_elapsed_ms(started), error=error)
