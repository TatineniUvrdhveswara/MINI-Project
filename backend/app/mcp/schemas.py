from pydantic import BaseModel, ConfigDict, Field


class PaperRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    source: str
    paper_url: str | None = None
    pdf_url: str | None = None
    full_text_available: bool = False


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, object]
    source: str


class SourceSearchResult(BaseModel):
    source: str
    papers: list[PaperRecord] = Field(default_factory=list)
    duration_ms: int
    error: str | None = None

