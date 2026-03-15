from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from feature_achievement.api.main import app
from feature_achievement.api.routers import ask as ask_router
from feature_achievement.db.engine import get_session


class DummySession:
    pass


@pytest.fixture
def client() -> Iterator[TestClient]:
    def override_db() -> Iterator[DummySession]:
        yield DummySession()

    app.dependency_overrides[get_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "query_type": "term",
        "term": "Actuator",
        "run_id": 7,
        "llm_enabled": False,
    }
    body.update(overrides)
    return body


def test_ask_api_returns_404_for_missing_run(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=404, detail="Run not found")

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_ask_api_returns_409_for_version_mismatch(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=409, detail="version mismatch")

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "version mismatch"


def test_ask_api_returns_422_when_no_seed_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=422, detail="No seed chapters found")

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "No seed chapters found"


def test_ask_api_term_flow_success_with_llm(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "cluster.v1",
            "query": "Actuator",
            "query_type": "term",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {"seed_chapter_ids": ["spring::ch1"], "seed_reason": "term_ilike"},
            "chapters": [
                {
                    "chapter_id": "spring::ch1",
                    "book_id": "spring",
                    "title": "Actuator",
                    "chapter_text": "text",
                    "chapter_index_text": "index",
                }
            ],
            "edges": [],
            "evidence": {
                "sections": [
                    {
                        "chapter_id": "spring::ch1",
                        "section_id": "spring::ch1::s1",
                        "title_norm": "actuator",
                        "score": 1.0,
                    }
                ],
                "bullets": [
                    {
                        "chapter_id": "spring::ch1",
                        "section_id": "spring::ch1::s1",
                        "bullet_id": "spring::ch1::s1::b1",
                        "text_norm": "actuator endpoint",
                        "score": 1.0,
                        "source_refs": None,
                    }
                ],
            },
            "constraints": {},
        }

    def fake_ask_qwen(
        query: str,
        query_type: str,
        cluster: dict[str, object],
        retrieval_term: str | None,
        model: str,
        timeout_ms: int,
    ) -> str:
        captured["query"] = query
        captured["query_type"] = query_type
        captured["cluster"] = cluster
        captured["retrieval_term"] = retrieval_term
        captured["model"] = model
        captured["timeout_ms"] = timeout_ms
        return "answer ok"

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(ask_router, "ask_qwen", fake_ask_qwen)

    response = client.post(
        "/ask",
        json=_payload(llm_enabled=True, return_cluster=True, return_graph_fragment=True),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] == "answer ok"
    assert body["query_type"] == "term"
    assert body["meta"]["schema_version"] == "cluster.v1"
    assert body["evidence"]["bullets"][0]["source_refs"] is None
    assert body["graph_fragment"]["nodes"] == [
        {"id": "spring::ch1", "book_id": "spring", "title": "Actuator"}
    ]
    assert body["graph_fragment"]["edges"] == []
    assert captured["query"] == 'Explain the term "Actuator" using the retrieved cluster.'
    assert captured["query_type"] == "term"
    assert captured["retrieval_term"] == "Actuator"


def test_ask_api_chapter_flow_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        captured["req"] = req
        return {
            "schema_version": "cluster.v1",
            "query": "Explain selected chapter",
            "query_type": "chapter",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {"seed_chapter_ids": ["spring::ch2"], "seed_reason": "chapter_selected"},
            "chapters": [
                {
                    "chapter_id": "spring::ch2",
                    "book_id": "spring",
                    "title": "Data Binding",
                    "chapter_text": "text",
                    "chapter_index_text": "index",
                }
            ],
            "edges": [],
            "evidence": {"sections": [], "bullets": []},
            "constraints": {},
        }

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)

    response = client.post(
        "/ask",
        json=_payload(
            query_type="chapter",
            chapter_id="spring::ch2",
            return_cluster=True,
            return_graph_fragment=False,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "chapter"
    assert body["cluster"]["seed"]["seed_reason"] == "chapter_selected"
    assert body["evidence"] == {"sections": [], "bullets": []}
    assert body["graph_fragment"] is None
    req = captured["req"]
    assert req.query_type == "chapter"
    assert req.chapter_id == "spring::ch2"
    assert req.query == 'Summarize the selected chapter "spring::ch2" using the retrieved cluster.'


def test_ask_api_records_llm_error_in_meta(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "cluster.v1",
            "query": "Actuator",
            "query_type": "term",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {"seed_chapter_ids": ["spring::ch1"], "seed_reason": "term_ilike"},
            "chapters": [],
            "edges": [],
            "evidence": {"sections": [], "bullets": []},
            "constraints": {},
        }

    def fake_ask_qwen(*args: object, **kwargs: object) -> str:
        raise RuntimeError("llm failure")

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(ask_router, "ask_qwen", fake_ask_qwen)

    response = client.post("/ask", json=_payload(llm_enabled=True))

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] is None
    assert body["meta"]["llm_error"] == "llm failure"


def test_ask_api_rejects_term_request_without_term(
    client: TestClient,
) -> None:
    response = client.post(
        "/ask",
        json={
            "query_type": "term",
            "user_query": "Tell me about Actuator",
            "run_id": 7,
            "llm_enabled": False,
        },
    )

    assert response.status_code == 422
    assert "term is required for term query_type" in response.text


def test_ask_api_chapter_flow_success_with_explicit_query(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        captured["req"] = req
        return {
            "schema_version": "cluster.v1",
            "query": "Explain selected chapter",
            "query_type": "chapter",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {"seed_chapter_ids": ["spring::ch2"], "seed_reason": "chapter_selected"},
            "chapters": [],
            "edges": [],
            "evidence": {"sections": [], "bullets": []},
            "constraints": {},
        }

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)

    response = client.post(
        "/ask",
        json=_payload(
            query_type="chapter",
            chapter_id="spring::ch2",
            query="Explain selected chapter",
            return_cluster=False,
            return_graph_fragment=False,
        ),
    )

    assert response.status_code == 200
    req = captured["req"]
    assert req.query == "Explain selected chapter"


def test_ask_api_rejects_chapter_request_without_chapter_id(
    client: TestClient,
) -> None:
    response = client.post(
        "/ask",
        json={
            "query_type": "chapter",
            "query": "Explain selected chapter",
            "run_id": 7,
            "llm_enabled": False,
        },
    )

    assert response.status_code == 422
    assert "chapter_id is required for chapter query_type" in response.text
