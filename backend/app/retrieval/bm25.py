import math
import re
from collections import Counter

from ..memory.schemas import PaperChunk


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_scores(query: str, chunks: list[PaperChunk], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    query_terms = set(tokenize(query))
    documents = {chunk.chunk_id: tokenize(chunk.text) for chunk in chunks}
    if not query_terms or not documents:
        return {}
    average_length = sum(len(tokens) for tokens in documents.values()) / len(documents)
    document_frequency = Counter(
        term for tokens in documents.values() for term in query_terms if term in set(tokens)
    )
    scores: dict[str, float] = {}
    total_documents = len(documents)
    for chunk_id, tokens in documents.items():
        term_counts = Counter(tokens)
        length = len(tokens) or 1
        score = 0.0
        for term in query_terms:
            frequency = term_counts.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total_documents - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            score += idf * (frequency * (k1 + 1)) / (
                frequency + k1 * (1 - b + b * length / max(average_length, 1))
            )
        if score > 0:
            scores[chunk_id] = score
    return scores
