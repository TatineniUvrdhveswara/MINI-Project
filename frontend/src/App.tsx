import { FormEvent, useEffect, useState } from "react";
import { createReport, generateAnswer, getMemoryStats, getSession, getSystemStatus, MemoryStats, QueryFilters, ResearchSession, retrieveEvidence, runCompleteWorkflow, searchLiterature, submitFinalDecision, submitQuery, SystemStatus } from "./api";

const initialFilters: QueryFilters = { sources: ["arxiv", "semantic_scholar"], analysis_type: "literature_review" };
const workflowStages = [
  ["query_validation", "Query validation"],
  ["initial_jev_decision", "Initial JEV decision"],
  ["mcp_literature_acquisition", "MCP literature acquisition"],
  ["scientific_memory_ingestion", "Scientific memory ingestion"],
  ["hybrid_evidence_retrieval", "Hybrid evidence retrieval"],
  ["answer_generation_evaluation", "Generation & evaluation"],
  ["report_built", "Report builder"],
  ["final_jev_decision", "Final JEV decision"],
] as const;
function App() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<QueryFilters>(initialFilters);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [memory, setMemory] = useState<MemoryStats | null>(null);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [sessionMessage, setSessionMessage] = useState("Ask a question to begin a traceable research workflow.");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [isRunningWorkflow, setIsRunningWorkflow] = useState(false);
  const [workflowDurationMs, setWorkflowDurationMs] = useState<number | null>(null);
  const currentStageIndex = workflowStages.findIndex(([stage]) => stage === (session?.current_stage ?? "query_validation"));
  const comparisonRows = [
    ["Context supplied to model", "Conversation and prompt context", "Conversation and prompt context", session?.retrieval ? `${session.retrieval.context.length.toLocaleString()} chars of selected evidence` : "Run a query to measure"],
    ["Retrieval candidates", "Model-dependent or tool-dependent", "Model-dependent or tool-dependent", session?.retrieval ? `${session.retrieval.merged_candidates} merged (${session.retrieval.dense_candidates} dense + ${session.retrieval.bm25_candidates} BM25)` : "Run a query to measure"],
    ["Evidence relevance", "No research score by default", "No research score by default", session?.evaluation ? `${(session.evaluation.relevance * 100).toFixed(0)}% relevance` : "Run a query to measure"],
    ["Evidence coverage", "Not automatically measured", "Not automatically measured", session?.evaluation ? `${(session.evaluation.evidence_coverage * 100).toFixed(0)}% coverage` : "Run a query to measure"],
    ["Citation support", "Depends on mode and prompt", "Depends on mode and prompt", session?.evaluation ? `${(session.evaluation.citation_support * 100).toFixed(0)}% supported · ${session.citations.length} citations` : "Run a query to measure"],
    ["Persistent memory", "Product/workspace dependent", "Product/workspace dependent", `${memory?.papers ?? "—"} papers · ${memory?.chunks ?? "—"} chunks`],
    ["Grounding check", "Usually requires an additional evaluation step", "Usually requires an additional evaluation step", session?.answer ? (session.answer.grounded ? "Grounded in selected evidence" : "Not grounded") : "Run a query to measure"],
    ["End-to-end workflow", "Not a research pipeline by default", "Not a research pipeline by default", session?.status === "completed" ? `${workflowDurationMs ? `${(workflowDurationMs / 1000).toFixed(1)}s` : "Completed"} · report generated` : "Run a query to measure"],
  ] as const;

  useEffect(() => {
    getSystemStatus().then(setStatus).catch((reason: Error) => setError(reason.message));
    getMemoryStats().then(setMemory).catch((reason: Error) => setError(reason.message));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    const workflowStartedAt = performance.now();
    try {
      const result = await submitQuery(query, filters);
      setSession(result.session);
      setSessionMessage(result.session.message);
      setIsRunningWorkflow(true);
      let current = (await runCompleteWorkflow(result.session.session_id)).session;
      setSession(current);
      setSessionMessage(current.message);
      while (current.status === "processing") {
        await new Promise((resolve) => setTimeout(resolve, 700));
        current = (await getSession(result.session.session_id)).session;
        setSession(current);
        setSessionMessage(current.message);
      }
      if (current.status === "failed") {
        throw new Error(current.message);
      }
      setWorkflowDurationMs(performance.now() - workflowStartedAt);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to submit query.");
    } finally {
      setIsSubmitting(false);
      setIsRunningWorkflow(false);
    }
  }

  async function handleLiteratureSearch() {
    if (!session) return;
    setError("");
    setIsSearching(true);
    try {
      const result = await searchLiterature(session.session_id);
      setSession(result.session);
      setSessionMessage(result.session.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to search literature.");
    } finally {
      setIsSearching(false);
    }
  }

  async function handleFinalDecision(sufficient: boolean) {
    if (!session) return;
    try {
      const result = await submitFinalDecision(session.session_id, sufficient);
      setSession(result);
      setSessionMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to record final decision.");
    }
  }

  async function handleRetrieveEvidence() {
    if (!session) return;
    setError("");
    setIsRetrieving(true);
    try {
      const result = await retrieveEvidence(session.session_id, query || session.query);
      setSession(result.session);
      setSessionMessage(result.session.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to retrieve evidence.");
    } finally {
      setIsRetrieving(false);
    }
  }

  async function handleGenerateAnswer() {
    if (!session) return;
    setError("");
    setIsGenerating(true);
    try {
      const result = await generateAnswer(session.session_id, query || session.query);
      setSession(result.session);
      setSessionMessage(result.session.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to generate answer.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleCreateReport() {
    if (!session) return;
    setError("");
    setIsReporting(true);
    try {
      const result = await createReport(session.session_id);
      setSession(result.session);
      setSessionMessage(result.session.message);
      const blob = new Blob([result.report.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `research-report-${session.session_id.slice(0, 8)}.md`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to build report.");
    } finally {
      setIsReporting(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">RA</span><div><strong>Research Assistant</strong><small>Scientific literature intelligence</small></div></div>
        <span className="environment-badge">{status?.environment ?? "connecting"}</span>
      </header>
      <main className="content">
        <section className="hero">
          <p className="eyebrow">MODULE 1 / RESEARCH WORKSPACE</p>
          <h1>Turn a research question into an evidence trail.</h1>
          <p className="hero-copy">Submit a focused question and prepare a transparent workflow for literature acquisition, retrieval, synthesis, and evaluation.</p>
        </section>
        <div className="workspace-grid">
          <form className="query-card" onSubmit={handleSubmit}>
            <div className="card-heading"><div><p className="eyebrow">Research query</p><h2>What do you want to investigate?</h2></div><span className="step">01</span></div>
            <label htmlFor="query">Question</label>
            <textarea id="query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Compare recent adaptive RAG approaches and identify potential research gaps." minLength={10} maxLength={2000} required />
            <div className="form-grid">
              <div><label htmlFor="analysis">Analysis type</label><select id="analysis" value={filters.analysis_type} onChange={(event) => setFilters({ ...filters, analysis_type: event.target.value as QueryFilters["analysis_type"] })}><option value="literature_review">Literature review</option><option value="paper_comparison">Paper comparison</option><option value="methodology_analysis">Methodology analysis</option><option value="trend_analysis">Trend analysis</option><option value="research_gaps">Research gaps</option></select></div>
              <div><label htmlFor="domain">Domain <span>(optional)</span></label><input id="domain" value={filters.domain ?? ""} onChange={(event) => setFilters({ ...filters, domain: event.target.value || undefined })} placeholder="e.g. machine learning" /></div>
            </div>
            <div className="form-grid"><div><label htmlFor="year-from">From year</label><input id="year-from" type="number" min="1900" max="2100" value={filters.year_from ?? ""} onChange={(event) => setFilters({ ...filters, year_from: event.target.value ? Number(event.target.value) : undefined })} /></div><div><label htmlFor="year-to">To year</label><input id="year-to" type="number" min="1900" max="2100" value={filters.year_to ?? ""} onChange={(event) => setFilters({ ...filters, year_to: event.target.value ? Number(event.target.value) : undefined })} /></div></div>
            {error && <p className="error">{error}</p>}
            <button type="submit" disabled={isSubmitting || isRunningWorkflow}>{isSubmitting || isRunningWorkflow ? "Running complete workflow..." : "Run complete research workflow"} <span>→</span></button>
          </form>
          <aside className="side-column">
            <section className="status-card"><div className="card-heading"><div><p className="eyebrow">System health</p><h2>Diagnostics</h2></div><span className="online-dot" /></div>{status ? status.components.map((component) => <div className="status-row" key={component.name}><span>{component.name.replace("-", " ")}</span><strong className={`status-${component.status}`}>{component.status}</strong></div>) : <p className="muted">Checking services...</p>}{memory && <div className="memory-stats"><span><strong>{memory.papers}</strong> papers</span><span><strong>{memory.chunks}</strong> chunks</span><span><strong>{memory.embedded_chunks}</strong> embedded</span></div>}</section>
            <section className="status-card workflow-card"><p className="eyebrow">Current session</p><h2>Workflow status</h2><div className="progress-track"><span style={{ width: `${((currentStageIndex + 1) / workflowStages.length) * 100}%` }} /></div><p className="muted">{sessionMessage}</p><p className="muted">Backend stage: <strong>{session?.current_stage ?? "query_validation"}</strong></p><div className="stage-list">{workflowStages.map(([stage, label], index) => <span className={index < currentStageIndex ? "completed" : index === currentStageIndex ? "current" : ""} key={stage}>{index < currentStageIndex ? "✓" : index === currentStageIndex ? "●" : "○"} {label}</span>)}</div>{session?.initial_jev && <div className="decision-box"><strong>{session.initial_jev.action.replace(/_/g, " ")}</strong><span>{session.initial_jev.explanation}</span></div>}{session && <button className="secondary-button" type="button" onClick={handleLiteratureSearch} disabled={isSearching || isRunningWorkflow}>{isSearching ? "Searching sources..." : "Search connected sources"}</button>}{session && <button className="secondary-button" type="button" onClick={handleRetrieveEvidence} disabled={isRetrieving || isRunningWorkflow}>{isRetrieving ? "Retrieving evidence..." : "Retrieve hybrid evidence"}</button>}{session?.retrieval && <button className="secondary-button" type="button" onClick={handleGenerateAnswer} disabled={isGenerating || isRunningWorkflow}>{isGenerating ? "Generating answer..." : "Generate grounded answer"}</button>}{session?.answer && <button className="secondary-button" type="button" onClick={handleCreateReport} disabled={isReporting || isRunningWorkflow}>{isReporting ? "Building report..." : "Build & download report"}</button>}</section>
          </aside>
        </div>
        <section className="result-card">
          <div className="card-heading"><div><p className="eyebrow">Research output</p><h2>Report & citations</h2></div><span className="step">02</span></div>
          {session ? <div className="output-summary"><span className="session-id">Session {session.session_id.slice(0, 8)}…</span>{session.answer ? <div className="answer-box"><strong>{session.answer.provider} · {session.answer.model}</strong><p>{session.answer.answer}</p>{session.evaluation && <span>Evaluation score: {(session.evaluation.overall_score * 100).toFixed(0)}% · {session.evaluation.passed ? "passed" : "needs refinement"}</span>}</div> : <p>{session.report ?? `${session.papers.length} normalized papers acquired. Module 3 will process these records into persistent scientific memory.`}</p>}<div className="citation-empty">{session.citations.length} citations available</div>{session.retrieval && <div className="retrieval-summary"><strong>Hybrid retrieval</strong><span>{session.retrieval.dense_candidates} dense · {session.retrieval.bm25_candidates} BM25 · {session.retrieval.selected_evidence.length} selected</span>{session.retrieval.selected_evidence.map((evidence) => <div className="paper-row" key={evidence.chunk.chunk_id}><strong>{evidence.chunk.text}</strong><span>{evidence.chunk.paper_id} · page {evidence.chunk.page_start ?? "unknown"} · {evidence.retrieval_sources.join(" + ")}</span></div>)}</div>}{session.papers.slice(0, 3).map((paper) => <div className="paper-row" key={paper.paper_id}><strong>{paper.title}</strong><span>{paper.source} · {paper.year ?? "year unavailable"}</span></div>)}{session.answer && <div className="decision-actions"><button type="button" onClick={() => handleFinalDecision(Boolean(session.evaluation?.passed))}>Send evaluation to final decision</button><button type="button" className="secondary-button" onClick={() => handleFinalDecision(false)}>Request refinement</button></div>}</div> : <p className="muted">Submit a research question to create a session. Generated reports and source citations will be shown here.</p>}
        </section>
        <section className="comparison-dashboard">
          <div className="card-heading">
            <div><p className="eyebrow">Why this project</p><h2>Research assistant comparison</h2></div>
            <span className="step">03</span>
          </div>
          <p className="dashboard-intro">Run the same question through this application and compare observable research metrics. ChatGPT and Gemini values describe their general interaction model; the final column is measured from this session.</p>
          <div className="comparison-grid comparison-head">
            <span>Capability</span><strong>ChatGPT</strong><strong>Gemini</strong><strong>Our research assistant</strong>
          </div>
          {comparisonRows.map(([capability, chatgpt, gemini, ours]) => (
            <div className="comparison-grid comparison-row" key={capability}>
              <strong>{capability}</strong><span>{chatgpt}</span><span>{gemini}</span><span className="ours-cell">{ours}</span>
            </div>
          ))}
          <div className="dashboard-proof">
            <div><strong>{session?.retrieval ? session.retrieval.selected_evidence.length : "—"}</strong><span>selected evidence chunks</span></div>
            <div><strong>{session?.evaluation ? `${(session.evaluation.overall_score * 100).toFixed(0)}%` : "—"}</strong><span>overall research score</span></div>
            <div><strong>{session?.evaluation ? session.evaluation.supported_claims : "—"}</strong><span>supported claims</span></div>
            <div><strong>{session?.status === "completed" ? "PASS" : "—"}</strong><span>final workflow evaluation</span></div>
          </div>
          <p className="comparison-note">The dashboard does not invent ChatGPT or Gemini benchmark scores. It contrasts their general model interaction with measured retrieval, context, relevance, coverage, citation, grounding, and workflow results from this application.</p>
        </section>
      </main>
      <footer><span>Evidence first · Transparent by design</span><span>API v0.1.0</span></footer>
    </div>
  );
}

export default App;
