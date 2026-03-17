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
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=404, detail="Run not found")

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_ask_api_returns_409_for_version_mismatch(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=409, detail="version mismatch")

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "version mismatch"


def test_ask_api_returns_422_when_no_seed_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        raise HTTPException(status_code=422, detail="No seed chapters found")

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)
    response = client.post("/ask", json=_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "No seed chapters found"


def test_ask_api_term_flow_success_with_llm(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "cluster_payload": {
                "schema_version": "cluster.v1",
                "query": "Actuator",
                "query_type": "term",
                "run_id": 7,
                "enrichment_version": "v2_indexed_sections_bullets",
                "seed": {
                    "seed_chapter_ids": ["spring::ch1"],
                    "seed_reason": "term_ilike",
                },
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
                "constraints": {},
            },
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
            "retrieval_warnings": None,
            "narrowing_payload": {
                "suggested_terms": None,
                "suggested_term_diagnostics": None,
            },
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": "answer ok",
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

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


def test_ask_api_chapter_flow_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_chapter_flow(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        assert req is not None
        assert req.query_type == "chapter"
        assert req.chapter_id == "spring::ch2"
        assert (
            req.query
            == 'Summarize the selected chapter "spring::ch2" using the retrieved cluster.'
        )
        return {
            "cluster_payload": {
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
            "constraints": {},
            },
            "evidence": {"sections": [], "bullets": []},
            "retrieval_warnings": None,
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_chapter_flow", fake_run_chapter_flow)

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


def test_ask_api_records_llm_error_in_meta(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "cluster_payload": {
                "schema_version": "cluster.v1",
                "query": "Actuator",
                "query_type": "term",
                "run_id": 7,
                "enrichment_version": "v2_indexed_sections_bullets",
                "seed": {
                    "seed_chapter_ids": ["spring::ch1"],
                    "seed_reason": "term_ilike",
                },
                "chapters": [],
                "edges": [],
                "constraints": {},
            },
            "evidence": {"sections": [], "bullets": []},
            "retrieval_warnings": None,
            "narrowing_payload": {
                "suggested_terms": None,
                "suggested_term_diagnostics": None,
            },
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": "llm failure",
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

    response = client.post("/ask", json=_payload(llm_enabled=True))

    assert response.status_code == 200
    body = response.json()
    assert body["answer_markdown"] is None
    assert body["meta"]["llm_error"] == "llm failure"


def test_ask_api_blocks_broad_precise_term_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        _ = (args, kwargs)
        return {
            "cluster_payload": {
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
                "constraints": {},
            },
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
            "retrieval_warnings": {
                "state": "broad_blocked",
                "term_too_broad": True,
                "evidence_too_scattered": True,
                "suggested_terms": [
                    "data persistence",
                    "JdbcTemplate",
                    "Spring Data JPA",
                    "Spring Data",
                ],
                "suggested_term_diagnostics": [
                    {"term": "data persistence"},
                    {"term": "JdbcTemplate"},
                    {"term": "Spring Data JPA"},
                    {"term": "Spring Data"},
                ],
                "recommendation_reason": "spring_persistence",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "narrowing_payload": {
                "suggested_terms": [
                    "data persistence",
                    "JdbcTemplate",
                    "Spring Data JPA",
                    "Spring Data",
                ],
                "suggested_term_diagnostics": [
                    {"term": "data persistence"},
                    {"term": "JdbcTemplate"},
                    {"term": "Spring Data JPA"},
                    {"term": "Spring Data"},
                ],
                "recommendation_reason": "spring_persistence",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "response_state": "needs_narrower_term",
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

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
        "data persistence",
        "JdbcTemplate",
        "Spring Data JPA",
        "Spring Data",
    ]
    assert warnings["suggested_term_diagnostics"] == [
        {"term": "data persistence"},
        {"term": "JdbcTemplate"},
        {"term": "Spring Data JPA"},
        {"term": "Spring Data"},
    ]
    assert warnings["recommendation_reason"] == "spring_persistence"
    assert warnings["recommendation_source"] == "rule_based"
    assert warnings["recommendation_confidence"] == "heuristic"


def test_ask_api_allows_broad_definition_term_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "cluster_payload": {
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
                "constraints": {},
            },
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
            "retrieval_warnings": {
                "state": "broad_allowed",
                "term_too_broad": True,
                "evidence_too_scattered": True,
                "suggested_terms": [
                    "Actuator",
                    "JdbcTemplate",
                    "data persistence",
                    "Spring Security",
                ],
                "recommendation_reason": "spring_fallback",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "narrowing_payload": {
                "suggested_terms": [
                    "Actuator",
                    "JdbcTemplate",
                    "data persistence",
                    "Spring Security",
                ],
                "suggested_term_diagnostics": None,
                "recommendation_reason": "spring_fallback",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "response_state": "broad_overview",
            "response_guidance": (
                "Warning: retrieval is broad. Give only a concise "
                "high-level concept explanation."
            ),
            "answer_markdown": "broad overview answer",
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

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
    assert "suggested_term_diagnostics" not in warnings
    assert warnings["recommendation_reason"] == "spring_fallback"
    assert warnings["recommendation_source"] == "rule_based"
    assert warnings["recommendation_confidence"] == "heuristic"


def test_ask_api_falls_back_to_recommender_order_when_candidate_ranking_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "cluster_payload": {
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
                "constraints": {},
            },
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
            "retrieval_warnings": {
                "state": "broad_blocked",
                "term_too_broad": True,
                "evidence_too_scattered": True,
                "suggested_terms": [
                    "Spring Data",
                    "data persistence",
                    "JdbcTemplate",
                    "Spring Data JPA",
                ],
                "recommendation_reason": "spring_persistence",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "narrowing_payload": {
                "suggested_terms": [
                    "Spring Data",
                    "data persistence",
                    "JdbcTemplate",
                    "Spring Data JPA",
                ],
                "suggested_term_diagnostics": None,
                "recommendation_reason": "spring_persistence",
                "recommendation_source": "rule_based",
                "recommendation_confidence": "heuristic",
            },
            "response_state": "needs_narrower_term",
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

    response = client.post(
        "/ask",
        json=_payload(
            term="Spring",
            user_query="How does Spring implement data persistence?",
            llm_enabled=False,
        ),
    )

    assert response.status_code == 200
    warnings = response.json()["meta"]["retrieval_warnings"]
    assert warnings["suggested_terms"] == [
        "Spring Data",
        "data persistence",
        "JdbcTemplate",
        "Spring Data JPA",
    ]
    assert "suggested_term_diagnostics" not in warnings


def test_ask_api_retry_with_narrower_term_clears_blocked_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_term_flow(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        if getattr(req, "term", None) == "Spring":
            return {
                "cluster_payload": {
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
                    "constraints": {},
                },
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
                "retrieval_warnings": {
                    "state": "broad_blocked",
                    "term_too_broad": True,
                    "evidence_too_scattered": True,
                    "suggested_terms": [
                        "Spring Data",
                        "data persistence",
                        "JdbcTemplate",
                        "Spring Data JPA",
                    ],
                    "recommendation_reason": "spring_persistence",
                    "recommendation_source": "rule_based",
                    "recommendation_confidence": "heuristic",
                },
                "narrowing_payload": {
                    "suggested_terms": [
                        "Spring Data",
                        "data persistence",
                        "JdbcTemplate",
                        "Spring Data JPA",
                    ],
                    "suggested_term_diagnostics": None,
                    "recommendation_reason": "spring_persistence",
                    "recommendation_source": "rule_based",
                    "recommendation_confidence": "heuristic",
                },
                "response_state": "needs_narrower_term",
                "response_guidance": None,
                "answer_markdown": None,
                "llm_error": None,
            }

        return {
            "cluster_payload": {
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
                "constraints": {},
            },
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book1::ch2"},
                    {"chapter_id": "book1::ch5"},
                ],
            },
            "retrieval_warnings": None,
            "narrowing_payload": {
                "suggested_terms": None,
                "suggested_term_diagnostics": None,
            },
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_term_flow", fake_run_term_flow)

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
    def fake_run_chapter_flow(*args: object, **kwargs: object) -> dict[str, object]:
        req = kwargs.get("req")
        assert req is not None
        assert req.query == "Explain selected chapter"
        return {
            "cluster_payload": {
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
            "constraints": {},
            },
            "evidence": {"sections": [], "bullets": []},
            "retrieval_warnings": None,
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    monkeypatch.setattr(ask_router, "run_chapter_flow", fake_run_chapter_flow)

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
