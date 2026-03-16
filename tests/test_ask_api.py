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
        response_guidance: str | None,
        model: str,
        timeout_ms: int,
    ) -> str:
        captured["query"] = query
        captured["query_type"] = query_type
        captured["cluster"] = cluster
        captured["retrieval_term"] = retrieval_term
        captured["response_guidance"] = response_guidance
        captured["model"] = model
        captured["timeout_ms"] = timeout_ms
        return "answer ok"

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(ask_router, "ask_qwen", fake_ask_qwen)

    response = client.post(
        "/ask",
        json=_payload(
            llm_enabled=True, return_cluster=True, return_graph_fragment=True
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] == "answer ok"
    assert body["query_type"] == "term"
    assert body["meta"]["schema_version"] == "cluster.v1"
    assert "retrieval_warnings" not in body["meta"]
    assert body["evidence"]["bullets"][0]["source_refs"] is None
    assert body["graph_fragment"]["nodes"] == [
        {"id": "spring::ch1", "book_id": "spring", "title": "Actuator"}
    ]
    assert body["graph_fragment"]["edges"] == []
    assert (
        captured["query"] == 'Explain the term "Actuator" using the retrieved cluster.'
    )
    assert captured["query_type"] == "term"
    assert captured["retrieval_term"] == "Actuator"
    assert captured["response_guidance"] is None


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
            "seed": {
                "seed_chapter_ids": ["spring::ch2"],
                "seed_reason": "chapter_selected",
            },
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
    assert (
        req.query
        == 'Summarize the selected chapter "spring::ch2" using the retrieved cluster.'
    )


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


def test_ask_api_blocks_broad_precise_term_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "cluster.v1",
            "query": "How does Spring implement data persistence?",
            "query_type": "term",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {
                "seed_chapter_ids": [
                    "book0::ch1",
                    "book1::ch2",
                    "book2::ch3",
                    "book0::ch4",
                    "book1::ch5",
                ],
                "seed_reason": "term_ilike",
            },
            "chapters": [
                {"chapter_id": "book0::ch1", "book_id": "book0", "title": "A"},
                {"chapter_id": "book1::ch2", "book_id": "book1", "title": "B"},
                {"chapter_id": "book2::ch3", "book_id": "book2", "title": "C"},
                {"chapter_id": "book0::ch4", "book_id": "book0", "title": "D"},
                {"chapter_id": "book1::ch5", "book_id": "book1", "title": "E"},
            ],
            "edges": [],
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book0::ch1"},
                    {"chapter_id": "book1::ch2"},
                    {"chapter_id": "book2::ch3"},
                    {"chapter_id": "book0::ch4"},
                    {"chapter_id": "book1::ch5"},
                ],
            },
            "constraints": {},
        }

    def fake_ask_qwen(*args: object, **kwargs: object) -> str:
        raise AssertionError("ask_qwen should not be called for blocked broad requests")

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(ask_router, "ask_qwen", fake_ask_qwen)

    response = client.post(
        "/ask",
        json=_payload(
            term="Spring",
            user_query="How does Spring implement data persistence?",
            llm_enabled=True,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] is None
    assert body["meta"]["response_state"] == "needs_narrower_term"
    warnings = body["meta"]["retrieval_warnings"]
    assert warnings["state"] == "broad_blocked"
    assert warnings["term_too_broad"] is True
    assert warnings["suggested_terms"] == [
        "Spring Data",
        "data persistence",
        "JdbcTemplate",
        "Spring Data JPA",
    ]
    assert warnings["recommendation_reason"] == "spring_persistence"
    assert warnings["recommendation_source"] == "rule_based"
    assert warnings["recommendation_confidence"] == "heuristic"


def test_ask_api_allows_broad_definition_term_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "cluster.v1",
            "query": "What is Spring?",
            "query_type": "term",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {
                "seed_chapter_ids": [
                    "book0::ch1",
                    "book1::ch2",
                    "book2::ch3",
                    "book0::ch4",
                    "book1::ch5",
                ],
                "seed_reason": "term_ilike",
            },
            "chapters": [
                {"chapter_id": "book0::ch1", "book_id": "book0", "title": "A"},
                {"chapter_id": "book1::ch2", "book_id": "book1", "title": "B"},
                {"chapter_id": "book2::ch3", "book_id": "book2", "title": "C"},
                {"chapter_id": "book0::ch4", "book_id": "book0", "title": "D"},
                {"chapter_id": "book1::ch5", "book_id": "book1", "title": "E"},
            ],
            "edges": [],
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book0::ch1"},
                    {"chapter_id": "book1::ch2"},
                    {"chapter_id": "book2::ch3"},
                    {"chapter_id": "book0::ch4"},
                    {"chapter_id": "book1::ch5"},
                ],
            },
            "constraints": {},
        }

    def fake_ask_qwen(
        query: str,
        query_type: str,
        cluster: dict[str, object],
        retrieval_term: str | None,
        response_guidance: str | None,
        model: str,
        timeout_ms: int,
    ) -> str:
        captured["query"] = query
        captured["response_guidance"] = response_guidance
        captured["retrieval_term"] = retrieval_term
        _ = (query_type, cluster, model, timeout_ms)
        return "broad overview answer"

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(ask_router, "ask_qwen", fake_ask_qwen)

    response = client.post(
        "/ask",
        json=_payload(
            term="Spring",
            user_query="What is Spring?",
            llm_enabled=True,
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] == "broad overview answer"
    assert body["meta"]["response_state"] == "broad_overview"
    warnings = body["meta"]["retrieval_warnings"]
    assert warnings["state"] == "broad_allowed"
    assert warnings["suggested_terms"] == [
        "Actuator",
        "JdbcTemplate",
        "data persistence",
        "Spring Security",
    ]
    assert warnings["recommendation_reason"] == "spring_fallback"
    assert warnings["recommendation_source"] == "rule_based"
    assert warnings["recommendation_confidence"] == "heuristic"
    assert captured["query"] == "What is Spring?"
    assert captured["retrieval_term"] == "Spring"
    assert "high-level concept explanation" in str(captured["response_guidance"])


def test_ask_api_retry_with_narrower_term_clears_blocked_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        if getattr(req, "term", None) == "Spring":
            return {
                "schema_version": "cluster.v1",
                "query": "How does Spring implement data persistence?",
                "query_type": "term",
                "run_id": 7,
                "enrichment_version": "v2_indexed_sections_bullets",
                "seed": {
                    "seed_chapter_ids": [
                        "book0::ch1",
                        "book1::ch2",
                        "book2::ch3",
                        "book0::ch4",
                        "book1::ch5",
                    ],
                    "seed_reason": "term_ilike",
                },
                "chapters": [
                    {"chapter_id": "book0::ch1", "book_id": "book0", "title": "A"},
                    {"chapter_id": "book1::ch2", "book_id": "book1", "title": "B"},
                    {"chapter_id": "book2::ch3", "book_id": "book2", "title": "C"},
                    {"chapter_id": "book0::ch4", "book_id": "book0", "title": "D"},
                    {"chapter_id": "book1::ch5", "book_id": "book1", "title": "E"},
                ],
                "edges": [],
                "evidence": {
                    "sections": [],
                    "bullets": [
                        {"chapter_id": "book0::ch1"},
                        {"chapter_id": "book1::ch2"},
                        {"chapter_id": "book2::ch3"},
                        {"chapter_id": "book0::ch4"},
                        {"chapter_id": "book1::ch5"},
                    ],
                },
                "constraints": {},
            }

        return {
            "schema_version": "cluster.v1",
            "query": "How does Spring implement data persistence?",
            "query_type": "term",
            "run_id": 7,
            "enrichment_version": "v2_indexed_sections_bullets",
            "seed": {
                "seed_chapter_ids": ["book1::ch2", "book1::ch5"],
                "seed_reason": "term_ilike",
            },
            "chapters": [
                {"chapter_id": "book1::ch2", "book_id": "book1", "title": "B"},
                {"chapter_id": "book1::ch5", "book_id": "book1", "title": "E"},
            ],
            "edges": [],
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book1::ch2"},
                    {"chapter_id": "book1::ch5"},
                ],
            },
            "constraints": {},
        }

    monkeypatch.setattr(ask_router, "build_cluster", fake_build_cluster)

    blocked_response = client.post(
        "/ask",
        json=_payload(
            term="Spring",
            user_query="How does Spring implement data persistence?",
            llm_enabled=False,
        ),
    )
    assert blocked_response.status_code == 200
    blocked_body = blocked_response.json()
    assert blocked_body["meta"]["response_state"] == "needs_narrower_term"
    assert blocked_body["meta"]["retrieval_warnings"]["suggested_terms"] == [
        "Spring Data",
        "data persistence",
        "JdbcTemplate",
        "Spring Data JPA",
    ]

    retry_response = client.post(
        "/ask",
        json=_payload(
            term="data persistence",
            user_query="How does Spring implement data persistence?",
            llm_enabled=False,
        ),
    )
    assert retry_response.status_code == 200
    retry_body = retry_response.json()
    assert retry_body["meta"]["schema_version"] == "cluster.v1"
    assert "response_state" not in retry_body["meta"]
    assert "retrieval_warnings" not in retry_body["meta"]


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
            "seed": {
                "seed_chapter_ids": ["spring::ch2"],
                "seed_reason": "chapter_selected",
            },
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
