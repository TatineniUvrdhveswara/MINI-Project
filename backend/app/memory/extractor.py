from pathlib import Path

import pymupdf


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")
    pages: list[tuple[int, str]] = []
    with pymupdf.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            text = " ".join(page.get_text("text").split())
            if text:
                pages.append((index, text))
    return pages
