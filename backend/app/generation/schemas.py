from pydantic import BaseModel, Field


class GeneratedAnswer(BaseModel):
    answer: str
    provider: str
    model: str
    citation_ids: list[str] = Field(default_factory=list)
    grounded: bool = True


class EvaluationResult(BaseModel):
    relevance: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    citation_support: float = Field(ge=0, le=1)
    factual_consistency: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    supported_claims: int
    unsupported_claims: int
    warnings: list[str] = Field(default_factory=list)
    passed: bool


class GenerationResponse(BaseModel):
    answer: GeneratedAnswer
    evaluation: EvaluationResult | None = None
