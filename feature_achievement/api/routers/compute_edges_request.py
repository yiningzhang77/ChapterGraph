from enum import Enum

from pydantic import BaseModel, model_validator


class CandidateGeneratorType(str, Enum):
    tfidf_token = "tfidf_token"


class SimilarityType(str, Enum):
    embedding = "embedding"
    tfidf = "tfidf"


class ComputeEdgesRequest(BaseModel):
    book_ids: list[str]
    enrichment_version: str = "v2_indexed_sections_bullets"

    candidate_generator: CandidateGeneratorType = CandidateGeneratorType.tfidf_token
    similarity: SimilarityType = SimilarityType.embedding
    embedding_model: str | None = None

    min_score: float = 0.1

    @model_validator(mode="after")
    def validate_strategy_options(self):
        if self.similarity == SimilarityType.embedding:
            self.embedding_model = self.embedding_model or "all-MiniLM-L6-v2"
        elif self.embedding_model is not None:
            raise ValueError(
                "embedding_model is only allowed when similarity='embedding'"
            )
        return self
