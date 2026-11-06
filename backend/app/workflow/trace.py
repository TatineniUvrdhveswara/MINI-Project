from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from .schemas import WorkflowMetrics, WorkflowTrace


class WorkflowTraceStore:
    def __init__(self) -> None:
        self._traces: dict[UUID, list[WorkflowTrace]] = {}
        self._started: dict[UUID, float] = {}

    def start_session(self, session_id: UUID) -> None:
        self._traces[session_id] = []
        self._started[session_id] = perf_counter()

    def record(self, session_id: UUID, stage: str, status: str, detail: str, started: float) -> None:
        self._traces.setdefault(session_id, []).append(
            WorkflowTrace(
                stage=stage,
                status=status,
                started_at=datetime.now(timezone.utc),
                duration_ms=round((perf_counter() - started) * 1000),
                detail=detail,
            )
        )

    def traces(self, session_id: UUID) -> list[WorkflowTrace]:
        return self._traces.get(session_id, [])

    def metrics(
        self,
        session_id: UUID,
        papers: int,
        chunks: int,
        selected: int,
        citations: int,
        refinements: int,
    ) -> WorkflowMetrics:
        return WorkflowMetrics(
            session_id=str(session_id),
            total_duration_ms=round((perf_counter() - self._started.get(session_id, perf_counter())) * 1000),
            papers_considered=papers,
            retrieved_chunks=chunks,
            selected_evidence=selected,
            citations=citations,
            refinement_cycles=refinements,
            errors=sum(trace.status == "failed" for trace in self.traces(session_id)),
        )


workflow_traces = WorkflowTraceStore()
