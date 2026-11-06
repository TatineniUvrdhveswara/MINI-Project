from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowTrace(BaseModel):
    stage: str
    status: str
    started_at: datetime
    duration_ms: int
    detail: str


class WorkflowMetrics(BaseModel):
    session_id: str
    total_duration_ms: int
    papers_considered: int
    retrieved_chunks: int
    selected_evidence: int
    citations: int
    refinement_cycles: int
    token_usage: int | None = None
    estimated_cost: float | None = None
    errors: int


class ResearchReport(BaseModel):
    session_id: str
    title: str
    executive_summary: str
    answer: str
    evidence_summary: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    references: list[dict[str, str | int | None]] = Field(default_factory=list)
    evaluation_score: float | None = None
    generated_at: datetime


class ReportResponse(BaseModel):
    report: ResearchReport
    markdown: str
