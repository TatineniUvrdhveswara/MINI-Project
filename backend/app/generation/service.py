from .evaluator import evaluate_answer
from .provider import LLMProvider
from .schemas import EvaluationResult, GeneratedAnswer
from ..retrieval.schemas import RetrievalResponse


class GenerationService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def generate(
        self, query: str, retrieval: RetrievalResponse
    ) -> tuple[GeneratedAnswer, EvaluationResult]:
        answer = self.provider.generate(query, retrieval)
        return answer, evaluate_answer(query, answer, retrieval)


generation_service = GenerationService(LLMProvider())
