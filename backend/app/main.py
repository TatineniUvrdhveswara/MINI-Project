from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .schemas import (
    ComponentStatus,
    Citation,
    AutomatedWorkflowResponse,
    FinalDecisionRequest,
    LiteratureSearchRequest,
    LiteratureSearchResponse,
    MCPToolsResponse,
    MemoryIngestionResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStats,
    GenerationRequest,
    SessionGenerationResponse,
    SessionReportResponse,
    RetrievalRequest,
    SessionRetrievalResponse,
    ResearchQueryRequest,
    ResearchQueryResponse,
    ResearchSession,
    SystemStatusResponse,
    WorkflowStatus,
)
from .store import session_store
from .jev import JEVDecisionEngine
from .mcp_service import MCPService
from .paper_store import paper_store
from .memory.embeddings import embedding_provider
from .memory.service import MemoryService
from .memory.store import scientific_memory
from .retrieval.service import HybridRetrievalService
from .generation.service import generation_service
from .workflow.report import build_report, render_markdown
from .workflow.schemas import WorkflowMetrics, WorkflowTrace
from .workflow.trace import workflow_traces
import logging
from time import perf_counter

settings = get_settings()
mcp_service = MCPService()
jev_engine = JEVDecisionEngine()
memory_service = MemoryService(scientific_memory, embedding_provider)
retrieval_service = HybridRetrievalService(scientific_memory, embedding_provider)
app = FastAPI(
    title=settings.app_name,
    description="API foundation for the MCP-based agentic scientific research assistant.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix=settings.api_prefix)
logger = logging.getLogger(__name__)


@app.get("/health", tags=["diagnostics"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/status", response_model=SystemStatusResponse, tags=["diagnostics"])
def get_system_status() -> SystemStatusResponse:
    return SystemStatusResponse(
        status="operational",
        environment=settings.environment,
        components=[
            ComponentStatus(
                name="api",
                status="operational",
                detail="FastAPI request handling is available.",
            ),
            ComponentStatus(
                name="workflow-orchestrator",
                status="ready",
                detail="Module 1 query contracts and Module 2 decision/search workflow are connected.",
            ),
            ComponentStatus(
                name="mcp-literature-sources",
                status="ready",
                detail="arXiv and Semantic Scholar tools are discoverable with bounded external calls.",
            ),
            ComponentStatus(
                name="jev-decision-adapter",
                status="provisional",
                detail="Safe adapter boundary is active; authoritative JEV specification is still required.",
            ),
            ComponentStatus(
                name="scientific-memory",
                status="ready",
                detail="SQLite metadata, PyMuPDF extraction, embeddings, and Chroma persistence are available.",
            ),
            ComponentStatus(
                name="hybrid-retrieval",
                status="ready",
                detail="Dense retrieval, BM25, candidate merging, reranking, and context construction are available.",
            ),
            ComponentStatus(
                name="llm-generation-evaluation",
                status="ready",
                detail="Grounded fallback generation, citation checks, and evidence evaluation are available.",
            ),
            ComponentStatus(
                name="reporting-monitoring",
                status="ready",
                detail="Structured reports, Markdown export, bounded refinement, and workflow metrics are available.",
            ),
        ],
    )


@router.post("/research/query", response_model=ResearchQueryResponse, status_code=201, tags=["research"])
def submit_research_query(payload: ResearchQueryRequest) -> ResearchQueryResponse:
    session = ResearchSession(query=payload.query, filters=payload.filters)
    session.initial_jev = jev_engine.decide_initial(
        memory_count=scientific_memory.stats().chunks,
        query=payload.query,
    )
    session.current_stage = "initial_jev_decision"
    session.message = session.initial_jev.explanation
    session_store.create(session)
    workflow_traces.start_session(session.session_id)
    workflow_traces.record(session.session_id, "initial_jev_decision", "completed", session.message, perf_counter())
    return ResearchQueryResponse(session=session)


@router.post(
    "/research/sessions/{session_id}/run",
    response_model=AutomatedWorkflowResponse,
    tags=["research", "workflow"],
)
def run_complete_workflow(
    session_id: str, background_tasks: BackgroundTasks
) -> AutomatedWorkflowResponse:
    session = _get_session(session_id)
    session.status = WorkflowStatus.PROCESSING
    session.current_stage = "mcp_literature_acquisition"
    session.message = "Workflow started. Acquiring scientific literature..."
    session_store.update(session)
    background_tasks.add_task(_execute_complete_workflow, session_id)
    return AutomatedWorkflowResponse(session=session)


def _execute_complete_workflow(session_id: str) -> None:
    try:
        _run_complete_workflow(session_id)
    except Exception as exc:
        logger.exception("Complete workflow failed for session %s", session_id)
        session = _get_session(session_id)
        session.status = WorkflowStatus.FAILED
        session.message = f"Workflow failed: {exc}"
        session_store.update(session)
        workflow_traces.record(session.session_id, session.current_stage, "failed", session.message, perf_counter())


def _run_complete_workflow(session_id: str) -> None:
    session = _get_session(session_id)
    session.current_stage = "mcp_literature_acquisition"
    session.message = "Workflow started. Acquiring scientific literature..."
    session_store.update(session)
    results = mcp_service.search(session.query, session.filters.sources, 5)
    session.source_results = results
    session.papers = mcp_service.store_papers(mcp_service.merge_unique(results))
    session.current_stage = "scientific_memory_ingestion"
    session.message = f"Indexing {len(session.papers)} acquired paper(s) into scientific memory..."
    session_store.update(session)
    ingestion_results = [
        memory_service.ingest(paper, paper_store.pdf_path(paper.paper_id))
        for paper in session.papers
    ]
    session.citations = [
        Citation(
            citation_id=paper.paper_id,
            title=paper.title,
            source=paper.source,
            url=paper.paper_url,
            year=paper.year,
        )
        for paper in session.papers
    ]
    failed_sources = [result.source for result in results if result.error]
    session.message = (
        f"Acquired {len(session.papers)} papers and indexed "
        f"{sum(result.chunks_embedded for result in ingestion_results)} chunks."
        if not failed_sources
        else f"Acquired literature with source limitations: {', '.join(failed_sources)}."
    )
    session_store.update(session)
    workflow_traces.record(session.session_id, "mcp_literature_acquisition", "completed", session.message, perf_counter())
    workflow_traces.record(
        session.session_id,
        "scientific_memory_ingestion",
        "completed",
        session.message,
        perf_counter(),
    )

    session.current_stage = "hybrid_evidence_retrieval"
    session.message = "Retrieving and reranking scientific evidence..."
    session_store.update(session)
    session.retrieval = retrieval_service.retrieve(session.query)
    session.message = f"Selected {len(session.retrieval.selected_evidence)} evidence chunk(s)."
    session_store.update(session)
    workflow_traces.record(session.session_id, "hybrid_evidence_retrieval", "completed", session.message, perf_counter())

    try:
        session.answer, session.evaluation = generation_service.generate(session.query, session.retrieval)
    except RuntimeError as exc:
        session.status = WorkflowStatus.FAILED
        session.current_stage = "answer_generation_evaluation"
        session.message = str(exc)
        session_store.update(session)
        workflow_traces.record(session.session_id, "answer_generation_evaluation", "failed", session.message, perf_counter())
        return
    session.current_stage = "answer_generation_evaluation"
    session.message = f"Generated an answer with evaluation score {session.evaluation.overall_score:.2f}."
    session_store.update(session)
    workflow_traces.record(session.session_id, "answer_generation_evaluation", "completed", session.message, perf_counter())

    report = build_report(session)
    session.report_document = report
    session.report = render_markdown(report)
    session.current_stage = "report_built"
    session.message = "Structured research report built successfully."
    session_store.update(session)
    workflow_traces.record(session.session_id, "report_builder", "completed", session.message, perf_counter())

    session.final_jev = jev_engine.decide_after_evaluation(
        papers_found=len(session.papers),
        evaluation_sufficient=session.evaluation.passed,
    )
    session.current_stage = "final_jev_decision"
    session.status = WorkflowStatus.COMPLETED
    session.message = session.final_jev.explanation
    session_store.update(session)
    workflow_traces.record(session.session_id, "final_jev_decision", "completed", session.message, perf_counter())
    return AutomatedWorkflowResponse(session=session)


@router.get("/mcp/tools", response_model=MCPToolsResponse, tags=["mcp"])
def discover_mcp_tools() -> MCPToolsResponse:
    return MCPToolsResponse(tools=mcp_service.discover_tools())


@router.post(
    "/research/sessions/{session_id}/literature",
    response_model=LiteratureSearchResponse,
    tags=["mcp", "research"],
)
def search_literature(
    session_id: str, payload: LiteratureSearchRequest
) -> LiteratureSearchResponse:
    session = _get_session(session_id)
    session.status = WorkflowStatus.PROCESSING
    session.current_stage = "mcp_literature_acquisition"
    results = mcp_service.search(session.query, session.filters.sources, payload.limit)
    session.source_results = results
    session.papers = mcp_service.store_papers(mcp_service.merge_unique(results))
    ingestion_results = [
        memory_service.ingest(paper, paper_store.pdf_path(paper.paper_id))
        for paper in session.papers
    ]
    session.citations = [
        Citation(
            citation_id=paper.paper_id,
            title=paper.title,
            source=paper.source,
            url=paper.paper_url,
            year=paper.year,
        )
        for paper in session.papers
    ]
    failed_sources = [result.source for result in results if result.error]
    session.message = (
        f"Acquired {len(session.papers)} unique papers; indexed "
        f"{sum(result.chunks_embedded for result in ingestion_results)} chunks."
        if not failed_sources
        else f"Literature acquisition completed with source failures: {', '.join(failed_sources)}."
    )
    session_store.update(session)
    return LiteratureSearchResponse(session=session)


@router.get("/papers", tags=["mcp", "research"])
def list_stored_papers() -> list[object]:
    return paper_store.list_papers()


@router.get("/memory/stats", response_model=MemoryStats, tags=["memory"])
def get_memory_stats() -> MemoryStats:
    return memory_service.stats()


@router.post("/memory/search", response_model=MemorySearchResponse, tags=["memory"])
def search_memory(payload: MemorySearchRequest) -> MemorySearchResponse:
    return MemorySearchResponse(results=memory_service.search(payload.query, payload.limit))


@router.post(
    "/research/sessions/{session_id}/ingest",
    response_model=MemoryIngestionResponse,
    tags=["memory", "research"],
)
def ingest_session_papers(session_id: str) -> MemoryIngestionResponse:
    session = _get_session(session_id)
    results = [
        memory_service.ingest(paper, paper_store.pdf_path(paper.paper_id))
        for paper in session.papers
    ]
    session.current_stage = "scientific_memory_ingestion"
    session.message = f"Processed {len(results)} paper(s) into scientific memory."
    session_store.update(session)
    return MemoryIngestionResponse(results=results)


@router.post(
    "/research/sessions/{session_id}/retrieve",
    response_model=SessionRetrievalResponse,
    tags=["retrieval", "research"],
)
def retrieve_session_evidence(
    session_id: str, payload: RetrievalRequest
) -> SessionRetrievalResponse:
    session = _get_session(session_id)
    retrieval = retrieval_service.retrieve(payload.query)
    session.retrieval = retrieval
    session.current_stage = "hybrid_evidence_retrieval"
    session.message = (
        f"Selected {len(retrieval.selected_evidence)} evidence chunk(s) from "
        f"{retrieval.merged_candidates} merged candidate(s)."
    )
    session_store.update(session)
    return SessionRetrievalResponse(session=session, retrieval=retrieval)


@router.post(
    "/research/sessions/{session_id}/generate",
    response_model=SessionGenerationResponse,
    tags=["generation", "evaluation", "research"],
)
def generate_session_answer(
    session_id: str, payload: GenerationRequest
) -> SessionGenerationResponse:
    session = _get_session(session_id)
    if session.retrieval is None:
        raise HTTPException(
            status_code=409,
            detail="Retrieve hybrid evidence before generating an answer.",
        )
    query = payload.query or session.query
    try:
        answer, evaluation = generation_service.generate(query, session.retrieval)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    session.answer = answer
    session.evaluation = evaluation
    session.current_stage = "answer_generation_evaluation"
    session.message = (
        f"Generated a grounded answer with evaluation score "
        f"{evaluation.overall_score:.2f}."
    )
    session_store.update(session)
    workflow_traces.record(
        session.session_id,
        "answer_generation_evaluation",
        "completed",
        session.message,
        perf_counter(),
    )
    return SessionGenerationResponse(session=session, answer=answer, evaluation=evaluation)


@router.post(
    "/research/sessions/{session_id}/report",
    response_model=SessionReportResponse,
    tags=["reports", "research"],
)
def create_session_report(session_id: str) -> SessionReportResponse:
    session = _get_session(session_id)
    report = build_report(session)
    markdown = render_markdown(report)
    session.report_document = report
    session.report = markdown
    session.current_stage = "report_built"
    session.message = "Structured research report built successfully."
    session_store.update(session)
    workflow_traces.record(session.session_id, "report_builder", "completed", session.message, perf_counter())
    return SessionReportResponse(session=session, report={"report": report, "markdown": markdown})


@router.get(
    "/research/sessions/{session_id}/traces",
    response_model=list[WorkflowTrace],
    tags=["monitoring", "research"],
)
def get_session_traces(session_id: str) -> list[WorkflowTrace]:
    session = _get_session(session_id)
    return workflow_traces.traces(session.session_id)


@router.get(
    "/research/sessions/{session_id}/metrics",
    response_model=WorkflowMetrics,
    tags=["monitoring", "research"],
)
def get_session_metrics(session_id: str) -> WorkflowMetrics:
    session = _get_session(session_id)
    return workflow_traces.metrics(
        session.session_id,
        len(session.papers),
        session.retrieval.merged_candidates if session.retrieval else 0,
        len(session.retrieval.selected_evidence) if session.retrieval else 0,
        len(session.citations),
        session.refinement_cycles,
    )


@router.post(
    "/research/sessions/{session_id}/final-decision",
    response_model=ResearchSession,
    tags=["research"],
)
def get_final_jev_decision(session_id: str, payload: FinalDecisionRequest) -> ResearchSession:
    session = _get_session(session_id)
    settings = get_settings()
    if not payload.evaluation_sufficient and session.refinement_cycles >= settings.max_refinement_cycles:
        session.final_jev = jev_engine.decide_after_evaluation(
            papers_found=len(session.papers),
            evaluation_sufficient=False,
        )
        session.current_stage = "refinement_limit_reached"
        session.status = WorkflowStatus.COMPLETED
        session.message = (
            f"Refinement limit ({settings.max_refinement_cycles}) reached; "
            "remaining evidence gaps are disclosed."
        )
        session_store.update(session)
        return session
    if not payload.evaluation_sufficient:
        session.refinement_cycles += 1
    session.final_jev = jev_engine.decide_after_evaluation(
        papers_found=len(session.papers),
        evaluation_sufficient=payload.evaluation_sufficient,
    )
    session.current_stage = "final_jev_decision"
    session.status = (
        WorkflowStatus.COMPLETED
        if payload.evaluation_sufficient
        else WorkflowStatus.PROCESSING
    )
    session.message = session.final_jev.explanation
    session_store.update(session)
    return session


def _get_session(session_id: str) -> ResearchSession:
    try:
        from uuid import UUID

        parsed_id = UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="session_id must be a valid UUID") from exc
    session = session_store.get(parsed_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session


@router.get(
    "/research/sessions/{session_id}",
    response_model=ResearchQueryResponse,
    tags=["research", "workflow"],
)
def get_research_session(session_id: str) -> ResearchQueryResponse:
    return ResearchQueryResponse(session=_get_session(session_id))


app.include_router(router)
