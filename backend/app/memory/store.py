import json
import math
import sqlite3
from pathlib import Path
from threading import Lock

try:
    import chromadb
except ImportError:
    chromadb = None

from ..config import get_settings
from .schemas import MemorySearchResult, MemoryStats, PaperChunk


class ScientificMemoryStore:
    def __init__(self, db_path: str | Path | None = None, vector_path: str | Path | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.metadata_db_path)
        self.vector_path = Path(vector_path or settings.vector_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_path.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize_sqlite()
        self.collection = (
            chromadb.PersistentClient(path=str(self.vector_path)).get_or_create_collection(
                name="scientific_chunks",
                metadata={"hnsw:space": "cosine"},
            )
            if chromadb is not None
            else None
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sqlite(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    ingestion_status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    embedding TEXT,
                    embedded INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(chunks)").fetchall()
            }
            if "embedding" not in columns:
                connection.execute("ALTER TABLE chunks ADD COLUMN embedding TEXT")

    def upsert_paper(self, paper_payload: dict, status: str = "processing") -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO papers (paper_id, payload, ingestion_status)
                VALUES (?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET payload=excluded.payload,
                    ingestion_status=excluded.ingestion_status
                """,
                (paper_payload["paper_id"], json.dumps(paper_payload), status),
            )

    def upsert_chunks(self, chunks: list[PaperChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Every chunk must have exactly one embedding")
        with self._lock, self._connect() as connection:
            for index, chunk in enumerate(chunks):
                connection.execute(
                    """
                    INSERT INTO chunks (chunk_id, paper_id, payload, embedding, embedded)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(chunk_id) DO UPDATE SET payload=excluded.payload,
                        embedding=excluded.embedding, embedded=1
                    """,
                    (chunk.chunk_id, chunk.paper_id, chunk.model_dump_json(), json.dumps(vectors[index])),
                )
            if chunks and self.collection is not None:
                self.collection.upsert(
                    ids=[chunk.chunk_id for chunk in chunks],
                    embeddings=vectors,
                    documents=[chunk.text for chunk in chunks],
                    metadatas=[
                        {
                            "paper_id": chunk.paper_id,
                            "source": chunk.source,
                            "page_start": chunk.page_start or 0,
                        }
                        for chunk in chunks
                    ],
                )

    def mark_paper_status(self, paper_id: str, status: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE papers SET ingestion_status=? WHERE paper_id=?",
                (status, paper_id),
            )

    def search(self, query_vector: list[float], limit: int = 5) -> list[MemorySearchResult]:
        if not query_vector:
            return []
        if self.collection is not None:
            result = self.collection.query(query_embeddings=[query_vector], n_results=limit)
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
        else:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT chunk_id, embedding FROM chunks WHERE embedded=1"
                ).fetchall()
            ranked = sorted(
                (
                    (row["chunk_id"], 1 - _cosine(query_vector, json.loads(row["embedding"])))
                    for row in rows
                    if row["embedding"]
                ),
                key=lambda item: item[1],
            )[:limit]
            ids = [item[0] for item in ranked]
            distances = [item[1] for item in ranked]
        if not ids:
            return []
        with self._connect() as connection:
            rows = {
                row["chunk_id"]: row["payload"]
                for row in connection.execute(
                    f"SELECT chunk_id, payload FROM chunks WHERE chunk_id IN ({','.join('?' for _ in ids)})",
                    ids,
                )
            }
        return [
            MemorySearchResult(
                chunk=PaperChunk.model_validate(json.loads(rows[chunk_id])),
                distance=distances[index] if index < len(distances) else None,
            )
            for index, chunk_id in enumerate(ids)
            if chunk_id in rows
        ]

    def list_chunks(self) -> list[PaperChunk]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM chunks WHERE embedded=1").fetchall()
        return [PaperChunk.model_validate(json.loads(row["payload"])) for row in rows]

    def stats(self) -> MemoryStats:
        with self._connect() as connection:
            papers = connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embedded = connection.execute("SELECT COUNT(*) FROM chunks WHERE embedded=1").fetchone()[0]
        return MemoryStats(
            papers=papers,
            chunks=chunks,
            embedded_chunks=embedded,
            storage="sqlite + chromadb",
            embedding_model=get_settings().embedding_model,
        )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


scientific_memory = ScientificMemoryStore()
