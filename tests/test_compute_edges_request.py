import pytest
from pydantic import ValidationError

from feature_achievement.api.routers.compute_edges_request import (
    CandidateGeneratorType,
    ComputeEdgesRequest,
    SimilarityType,
)


def test_request_defaults_to_embedding_with_default_model():
    req = ComputeEdgesRequest(book_ids=["spring-in-action"])
    assert req.similarity == SimilarityType.embedding
    assert req.embedding_model == "all-MiniLM-L6-v2"
    assert req.candidate_generator == CandidateGeneratorType.tfidf_token


def test_tfidf_rejects_embedding_model():
    with pytest.raises(ValidationError):
        ComputeEdgesRequest(
            book_ids=["spring-in-action"],
            similarity="tfidf",
            embedding_model="all-MiniLM-L6-v2",
        )


def test_invalid_similarity_is_rejected():
    with pytest.raises(ValidationError):
        ComputeEdgesRequest(
            book_ids=["spring-in-action"],
            similarity="bm25",
        )


def test_invalid_candidate_generator_is_rejected():
    with pytest.raises(ValidationError):
        ComputeEdgesRequest(
            book_ids=["spring-in-action"],
            candidate_generator="random_walk",
        )
