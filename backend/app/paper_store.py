import json
import re
from pathlib import Path
from threading import Lock
from typing import Any

from .config import get_settings
from .mcp.schemas import PaperRecord


class PaperStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().paper_storage_path)
        self.metadata_path = self.root / "papers.json"
        self._lock = Lock()

    def save_paper(self, paper: PaperRecord, pdf_bytes: bytes | None = None) -> PaperRecord:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            records = self._read_records()
            records[paper.paper_id] = paper.model_dump(mode="json")
            self.metadata_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
            if pdf_bytes:
                (self.root / f"{_safe_filename(paper.paper_id)}.pdf").write_bytes(pdf_bytes)
        return paper

    def list_papers(self) -> list[PaperRecord]:
        with self._lock:
            return [PaperRecord.model_validate(item) for item in self._read_records().values()]

    def pdf_path(self, paper_id: str) -> Path | None:
        path = self.root / f"{_safe_filename(paper_id)}.pdf"
        return path if path.exists() else None

    def _read_records(self) -> dict[str, dict[str, Any]]:
        if not self.metadata_path.exists():
            return {}
        return json.loads(self.metadata_path.read_text(encoding="utf-8"))


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", value)


paper_store = PaperStore()
