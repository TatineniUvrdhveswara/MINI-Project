from collections.abc import Sequence
import re

import httpx

from ..config import get_settings
from ..retrieval.schemas import RetrievalCandidate, RetrievalResponse
from .schemas import GeneratedAnswer


class GroundedFallbackProvider:
    name = "grounded_fallback"

    def generate(self, query: str, retrieval: RetrievalResponse) -> GeneratedAnswer:
        if not retrieval.selected_evidence:
            return GeneratedAnswer(
                answer=(
                    "Insufficient evidence is available in scientific memory to answer this "
                    "question. Acquire or ingest relevant papers before making a research claim."
                ),
                provider=self.name,
                model="grounded-fallback-v1",
                grounded=True,
            )
        citations: list[str] = []
        evidence_lines: list[str] = []
        for index, candidate in enumerate(retrieval.selected_evidence, start=1):
            citation_id = f"E{index}"
            citations.append(candidate.chunk.chunk_id)
            evidence_lines.append(
                f"- [{citation_id}] {candidate.chunk.text} "
                f"(paper {candidate.chunk.paper_id}, page {candidate.chunk.page_start or 'unknown'})"
            )
        answer = (
            f"## Evidence-grounded response\n\n"
            f"Question: {query}\n\n"
            f"The available indexed evidence provides the following relevant findings:\n"
            + "\n".join(evidence_lines)
            + "\n\nThis response is limited to the retrieved evidence. "
            "The cited chunks should be reviewed against the original papers before publication."
        )
        return GeneratedAnswer(
            answer=answer,
            provider=self.name,
            model="grounded-fallback-v1",
            citation_ids=citations,
            grounded=True,
        )


class LLMProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self._fallback = GroundedFallbackProvider()
        self._google_api_key = settings.google_api_key
        self._google_model = settings.google_model
        self._groq_api_key = settings.groq_api_key
        self._timeout = settings.request_timeout

    def generate(self, query: str, retrieval: RetrievalResponse) -> GeneratedAnswer:
        if self.provider == "grounded_fallback":
            return self._fallback.generate(query, retrieval)
        if not retrieval.selected_evidence:
            return self._fallback.generate(query, retrieval)
        if self.provider == "google":
            return self._generate_google(query, retrieval)
        if self.provider == "groq":
            try:
                return self._generate_groq(query, retrieval)
            except RuntimeError as groq_error:
                if not self._google_api_key:
                    raise
                try:
                    return self._generate_google(
                        query,
                        retrieval,
                        model=self._google_model,
                    )
                except RuntimeError as google_error:
                    raise RuntimeError(
                        f"Groq failed ({groq_error}); Google fallback failed ({google_error})."
                    ) from google_error
        raise RuntimeError(f"Unsupported LLM_PROVIDER '{self.provider}'.")

    def _generate_google(
        self,
        query: str,
        retrieval: RetrievalResponse,
        model: str | None = None,
    ) -> GeneratedAnswer:
        if not self._google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is required when LLM_PROVIDER=google.")
        prompt = _grounded_prompt(query, retrieval)
        selected_model = model or self.model
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{selected_model}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                params={"key": self._google_api_key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Google generation failed: {exc}") from exc
        return _generated_answer(text, "google", selected_model, retrieval)

    def _generate_groq(self, query: str, retrieval: RetrievalResponse) -> GeneratedAnswer:
        if not self._groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")
        prompt = _grounded_prompt(query, retrieval)
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._groq_api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Answer only from the supplied scientific evidence.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RuntimeError(
                    "Groq rate limit reached. Wait and retry, or select a different "
                    "configured provider/model."
                ) from exc
            raise RuntimeError(
                f"Groq generation failed with HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Groq generation failed: {exc}") from exc
        return _generated_answer(text, "groq", self.model, retrieval)


def _grounded_prompt(query: str, retrieval: RetrievalResponse) -> str:
    evidence = "\n\n".join(
        f"[{candidate.chunk.chunk_id}] {candidate.chunk.text} "
        f"(paper {candidate.chunk.paper_id}, page {candidate.chunk.page_start or 'unknown'})"
        for candidate in retrieval.selected_evidence
    )
    return (
        "Research question:\n"
        f"{query}\n\n"
        "Evidence records:\n"
        f"{evidence}\n\n"
        "Write a concise, accurate research answer using only these evidence records. "
        "Do not invent facts. Add one or more exact citation markers in the form "
        "[CITATION:chunk_id] after supported statements. If the evidence is insufficient, "
        "say so explicitly."
    )


def _generated_answer(
    text: str,
    provider: str,
    model: str,
    retrieval: RetrievalResponse,
) -> GeneratedAnswer:
    valid_ids = {candidate.chunk.chunk_id for candidate in retrieval.selected_evidence}
    citations = [
        citation_id
        for citation_id in re.findall(r"\[CITATION:([^\]]+)\]", text)
        if citation_id in valid_ids
    ]
    cleaned = re.sub(r"\[CITATION:([^\]]+)\]", r"[\1]", text).strip()
    citations = list(dict.fromkeys(citations))
    if not citations:
        citations = [candidate.chunk.chunk_id for candidate in retrieval.selected_evidence]
        cleaned = (
            f"{cleaned}\n\nSources: "
            + ", ".join(f"[{citation_id}]" for citation_id in citations)
        )
    return GeneratedAnswer(
        answer=cleaned,
        provider=provider,
        model=model,
        citation_ids=citations,
        grounded=True,
    )


llm_provider = LLMProvider()
