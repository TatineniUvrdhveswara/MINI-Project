from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .mcp.schemas import MCPTool, PaperRecord, SourceSearchResult
from .memory.schemas import IngestionResult, MemorySearchResult, MemoryStats
from .retrieval.schemas import RetrievalResponse
from .generation.schemas import EvaluationResult, GeneratedAnswer
from .workflow.schemas import ReportResponse, ResearchReport, WorkflowMetrics, WorkflowTrace


class AnalysisType(StrEnum):
    LITERATURE_REVIEW = "literature_review"
    PAPER_COMPARISON = "paper_comparison"
    METHODOLOGY_ANALYSIS = "methodology_analysis"
    TREND_ANALYSIS = "trend_analysis"
    RESEARCH_GAPS = "research_gaps"


class QueryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    sources: list[str] = Field(default_factory=list, max_length=10)
    domain: str | None = Field(default=None, max_length=120)
    analysis_type: AnalysisType = AnalysisType.LITERATURE_REVIEW

    @field_validator("sources")
    @classmethod
    def normalize_sources(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})

    @field_validator("year_to")
    @classmethod
    def validate_year_range(cls, value: int | None, info: Any) -> int | None:
        year_from = info.data.get("year_from")
        if value is not None and year_from is not None and value < year_from:
            raise ValueError("year_to must be greater than or equal to year_from")
        return value


class ResearchQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=10, max_length=2000)
    filters: QueryFilters = Field(default_factory=QueryFilters)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query must contain non-whitespace characters")
        return normalized


class Citation(BaseModel):
    citation_id: str
    title: str
    source: str
    url: str | None = None
    year: int | None = None


class WorkflowStatus(StrEnum):
    STARTED = "started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JEVAction(StrEnum):
    REUSE_OR_ACQUIRE = "reuse_or_acquire"
    ACQUIRE = "acquire"
    APPROVE = "approve"
    REFINE = "refine"
    STOP_INSUFFICIENT_EVIDENCE = "stop_insufficient_evidence"


class JEVDecision(BaseModel):
    action: JEVAction
    explanation: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    implementation: str


class ResearchSession(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    query: str
    filters: QueryFilters
    status: WorkflowStatus = WorkflowStatus.STARTED
    current_stage: str = "query_validation"
    message: str = "Query accepted. Workflow orchestration is ready."
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    citations: list[Citation] = Field(default_factory=list)
    report: str | None = None
    initial_jev: JEVDecision | None = None
    final_jev: JEVDecision | None = None
    papers: list[PaperRecord] = Field(default_factory=list)
    source_results: list[SourceSearchResult] = Field(default_factory=list)
    refinement_cycles: int = 0
    retrieval: RetrievalResponse | None = None
    answer: GeneratedAnswer | None = None
    evaluation: EvaluationResult | None = None
    report_document: ResearchReport | None = None
    workflow_traces: list[WorkflowTrace] = Field(default_factory=list)


class ResearchQueryResponse(BaseModel):
    session: ResearchSession


class LiteratureSearchRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


class LiteratureSearchResponse(BaseModel):
    session: ResearchSession


class AutomatedWorkflowResponse(BaseModel):
    session: ResearchSession


class FinalDecisionRequest(BaseModel):
    evaluation_sufficient: bool = False


class MCPToolsResponse(BaseModel):
    tools: list[MCPTool]


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]


class MemoryIngestionResponse(BaseModel):
    results: list[IngestionResult]


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)


class SessionRetrievalResponse(BaseModel):
    session: ResearchSession
    retrieval: RetrievalResponse


class GenerationRequest(BaseModel):
    query: str | None = Field(default=None, min_length=2, max_length=2000)


class SessionGenerationResponse(BaseModel):
    session: ResearchSession
    answer: GeneratedAnswer
    evaluation: EvaluationResult


class SessionReportResponse(BaseModel):
    session: ResearchSession
    report: ReportResponse


class ComponentStatus(BaseModel):
    name: str
    status: str
    detail: str


class SystemStatusResponse(BaseModel):
    status: str
    environment: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    components: list[ComponentStatus]
