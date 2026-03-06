from fastapi.testclient import TestClient

from feature_achievement.api.deps import RetrievalResources, get_retrieval_resources
from feature_achievement.api.main import app
from feature_achievement.api.routers import edges as edges_router
from feature_achievement.api.routers.compute_edges_request import ComputeEdgesRequest
from feature_achievement.db.engine import get_session
from feature_achievement.db.models import Run


class DummySession:
    def __init__(self):
        self.added: list[object] = []
        self.commit_calls = 0

    def add(self, obj: object):
        self.added.append(obj)

    def commit(self):
        self.commit_calls += 1

    def refresh(self, obj: object):
        if isinstance(obj, Run):
            obj.id = 1


def test_openapi_exposes_similarity_and_candidate_generator_enums():
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    similarity_schema = schemas["SimilarityType"]
    candidate_schema = schemas["CandidateGeneratorType"]
    request_schema = schemas["ComputeEdgesRequest"]

    assert similarity_schema["enum"] == ["embedding", "tfidf"]
    assert candidate_schema["enum"] == ["tfidf_token"]
    assert request_schema["properties"]["similarity"]["default"] == "embedding"


def test_compute_edges_uses_similarity_from_request_contract(monkeypatch):
    dummy_session = DummySession()
    captured: dict[str, str] = {}
    persisted: dict[str, object] = {}

    def override_db():
        yield dummy_session

    def override_resources():
        return RetrievalResources(
            enriched_books=[
                {
                    "book_id": "spring-in-action",
                    "chapters": [
                        {
                            "id": "spring-in-action::ch1",
                            "title": "t",
                            "chapter_text": "x",
                        }
                    ],
                }
            ],
            chapter_texts={"spring-in-action::ch1": "x"},
        )

    class RuntimeStub:
        pipeline = object()

    def fake_build_runtime(
        enriched_books: list[dict[str, object]],
        req: ComputeEdgesRequest,
    ):
        captured["similarity"] = req.similarity.value
        return RuntimeStub()

    def fake_generate_edges(
        enriched_books: list[dict[str, object]],
        pipeline: object,
    ):
        return [{"from": "spring-in-action::ch1", "to": "other::ch2", "score": 0.2, "type": "tfidf"}]

    def fake_persist_books_and_chapters(
        enriched_books: list[dict[str, object]],
        session: DummySession,
    ):
        persisted["books"] = enriched_books

    def fake_persist_edges(
        edges: list[dict[str, object]],
        run_id: int,
        session: DummySession,
    ):
        persisted["edges"] = edges
        persisted["run_id"] = run_id

    monkeypatch.setattr(edges_router, "build_retrieval_runtime", fake_build_runtime)
    monkeypatch.setattr(edges_router, "generate_edges", fake_generate_edges)
    monkeypatch.setattr(
        edges_router,
        "persist_books_and_chapters",
        fake_persist_books_and_chapters,
    )
    monkeypatch.setattr(edges_router, "persist_edges", fake_persist_edges)

    app.dependency_overrides[get_session] = override_db
    app.dependency_overrides[get_retrieval_resources] = override_resources
    try:
        with TestClient(app) as client:
            response = client.post(
                "/compute-edges",
                json={
                    "book_ids": ["spring-in-action"],
                    "similarity": "tfidf",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == 1
    assert body["count"] == 1
    assert captured["similarity"] == "tfidf"
    assert persisted["run_id"] == 1
    assert isinstance(dummy_session.added[0], Run)
    assert dummy_session.added[0].min_score == 0.1
    assert dummy_session.commit_calls == 1


def test_compute_edges_returns_400_when_book_ids_do_not_match(monkeypatch):
    dummy_session = DummySession()

    def override_db():
        yield dummy_session

    def override_resources():
        return RetrievalResources(
            enriched_books=[
                {
                    "book_id": "springboot-in-action",
                    "chapters": [
                        {
                            "id": "springboot-in-action::ch1",
                            "title": "t",
                            "chapter_text": "x",
                        }
                    ],
                }
            ],
            chapter_texts={"springboot-in-action::ch1": "x"},
        )

    app.dependency_overrides[get_session] = override_db
    app.dependency_overrides[get_retrieval_resources] = override_resources
    try:
        with TestClient(app) as client:
            response = client.post(
                "/compute-edges",
                json={
                    "book_ids": ["spring-in-action"],
                    "similarity": "embedding",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "No matching books for requested book_ids"
