# MCP-Based Agentic Research Assistant

This repository currently implements Modules 1–6 from the architecture in [README_MCP_Agentic_Research_Assistant.md](./README_MCP_Agentic_Research_Assistant.md).

## Module 1 scope

- React + TypeScript research workspace
- FastAPI query and session API
- Explicit Pydantic request/response contracts
- Query normalization and validation
- System health and component diagnostics
- Workflow status placeholder that clearly identifies downstream modules as planned
- Module 2 decision boundary with provisional JEV policy and final decision mapping
- Real MCP stdio server/client integration using the official MCP Python SDK
- MCP tools for arXiv, Semantic Scholar, paper metadata, and accessible PDF download
- Persistent normalized paper metadata and PDF storage under `backend/data/papers`
- Bounded external requests, source-level errors, deduplication, and citation propagation
- CORS configuration for local frontend development
- Backend unit/API tests

## Module 3: Persistent Scientific Memory

- PyMuPDF PDF extraction with page provenance
- Section-ready, overlapping chunk records
- Sentence Transformers embedding provider
- SQLite metadata and chunk source of truth
- ChromaDB persistent vector index when its native dependency is available
- Persistent SQLite cosine-search fallback for Python environments where Chroma native wheels are unavailable
- Memory statistics, ingestion, and semantic search APIs

## Module 4: Adaptive Hybrid RAG

- Dense retrieval from the Module 3 vector/scalar memory
- BM25 keyword retrieval implemented without an extra native dependency
- Candidate merging with source provenance
- Deterministic reranking using dense relevance, normalized BM25, and lexical overlap
- Top-k evidence selection
- Citation-aware context construction with paper and page provenance
- Session retrieval endpoint and frontend evidence trace

Endpoint:

```text
POST /api/v1/research/sessions/{session_id}/retrieve
```

The request body is `{"query": "your research question"}`. The response exposes dense/BM25/merged counts, selected evidence, ranking scores, retrieval sources, and the context passed to the next generation module.

Endpoints:

- `GET /api/v1/memory/stats`
- `POST /api/v1/memory/search`
- `POST /api/v1/research/sessions/{session_id}/ingest`
- `GET /api/v1/papers`

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` (or `http://localhost:5173`). The frontend connects to `http://127.0.0.1:8000/api/v1` by default; set `VITE_API_URL` to override it. Both local origins are allowed by the backend.

### Tests

```powershell
cd backend
pytest
```

## Module 2 manual test

1. Start the backend and frontend as above.
2. Enter a question with at least 10 characters and click **Start research workflow**.
3. Confirm the session shows an initial `acquire` decision and the diagnostics show MCP and JEV components.
4. Click **Search connected sources**. The first run may take up to the configured request timeout per source.
5. Confirm normalized papers and citations appear in **Report & citations**.
6. Use **Mark evidence sufficient** or **Request refinement** to record the final decision.

After literature acquisition, the API automatically sends downloaded PDFs through Module 3 ingestion. For a direct memory check, use:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/memory/stats
```

The first embedding run may download `sentence-transformers/all-MiniLM-L6-v2`. Runtime data is written to `backend/data/`, which is ignored by Git.

After memory contains indexed chunks, click **Retrieve hybrid evidence** in the workflow panel to run Module 4.

## Local scientific persistence

The application uses local SQLite and ChromaDB for persistent scientific memory:

- `backend/data/metadata.db` stores canonical paper records and chunk records.
- `backend/data/chroma` stores the persistent ChromaDB vector index when ChromaDB is available.
- The SQLite `chunks` table also stores each chunk's serialized text, paper ID, section, page range, year, source, and embedding.
- When ChromaDB cannot be installed for the active Python version, retrieval automatically uses the embeddings stored in SQLite with cosine similarity.
- `backend/data/papers` stores normalized paper metadata and permitted downloaded PDFs.

The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`. Keep the same embedding model for ingestion and query-time retrieval. Runtime data is ignored by Git and is created automatically when the backend starts.

To inspect the stored scientific memory:

```powershell
cd backend
python -c "import sqlite3; db=sqlite3.connect('data/metadata.db'); print(db.execute('SELECT COUNT(*) FROM papers').fetchone()[0], 'papers'); print(db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0], 'chunks')"
```

The application does not require PostgreSQL or a separate database server for local use.

## Module 5: LLM Generation & Answer Evaluation

- Provider-neutral generation boundary
- Deterministic grounded fallback provider for environments without an LLM key
- Evidence-only answer synthesis from Module 4 context
- Citation ID propagation and validation
- Relevance, evidence coverage, citation support, factual consistency, and completeness scores
- Unsupported-citation and no-evidence warnings
- Session generation endpoint and evaluation display

Endpoint:

```text
POST /api/v1/research/sessions/{session_id}/generate
```

The generation layer supports `grounded_fallback`, `google`, and `groq`. Google uses the Gemini `generateContent` API; Groq uses its OpenAI-compatible chat-completions API. Both receive only selected retrieval evidence and must return citation markers that match selected chunk IDs. With no selected evidence, the service returns an explicit insufficient-evidence response.

Configure one provider in the local-only `backend/.env` file. If Groq is rate-limited, the service automatically attempts Google Gemini when `GOOGLE_API_KEY` is configured:

```env
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=your-groq-key
GOOGLE_MODEL=gemini-3.1-flash-lite
GOOGLE_API_KEY=your-google-key
```

For Google Gemini, use a model returned by Google's `generateContent` model list:

```env
LLM_PROVIDER=google
LLM_MODEL=gemini-3.1-flash-lite
GOOGLE_API_KEY=your-google-key
```

Never commit `.env` or expose API keys in source control. Provider errors are surfaced as HTTP 503 responses instead of unhandled server tracebacks or fabricated answers. A Groq HTTP 429 means its rate limit has been reached; wait before retrying or select another available model/provider.

After retrieving evidence, click **Generate grounded answer**. Review the evaluation score and warnings before sending the evaluation to the final JEV decision.

## Module 6: Research Reports & Workflow Management

- Structured research report builder
- Executive summary, answer, evidence, limitations, evaluation score, and references
- Markdown export from the frontend
- Per-session workflow traces
- Latency, paper, chunk, evidence, citation, refinement, and error metrics
- Configurable bounded refinement cycles through `MAX_REFINEMENT_CYCLES`
- Report and monitoring endpoints:

```text
POST /api/v1/research/sessions/{session_id}/report
GET  /api/v1/research/sessions/{session_id}/traces
GET  /api/v1/research/sessions/{session_id}/metrics
```

After generating an answer, click **Build & download report**. The report remains grounded in the selected evidence and explicitly lists limitations when evidence or a real LLM provider is unavailable.

The initial and final decision implementation is intentionally labeled provisional until the project selects and documents an authoritative JEV specification. The source adapters use live public APIs; a source outage is displayed in the session instead of being hidden.

## Real MCP implementation

The backend now launches [app/mcp_server.py](./backend/app/mcp_server.py) as a separate stdio MCP server process using the official `mcp` Python SDK. [app/mcp_client.py](./backend/app/mcp_client.py) initializes an MCP `ClientSession`, discovers tools through `list_tools`, invokes tools through `call_tool`, and converts the returned JSON into application schemas.

The server provides:

- `search_arxiv`
- `search_semantic_scholar`
- `get_paper_metadata`
- `download_paper_pdf`

The literature endpoint stores every normalized paper in `backend/data/papers/papers.json`. If an accessible PDF URL is returned, its bytes are downloaded through the MCP PDF tool and stored beside the metadata. API keys are not committed; Semantic Scholar can run anonymously with stricter rate limits or use `SEMANTIC_SCHOLAR_API_KEY` from a local `.env`.
