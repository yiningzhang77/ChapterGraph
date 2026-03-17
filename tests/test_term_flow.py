from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import term_flow


def test_run_term_flow_returns_service_shape(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "_build_term_cluster",
        lambda **kwargs: {"cluster_payload": {"chapters": []}, "evidence": {"bullets": []}},
    )
    monkeypatch.setattr(
        term_flow,
        "_evaluate_term_quality",
        lambda **kwargs: {"retrieval_warnings": {"state": "normal"}},
    )
    monkeypatch.setattr(
        term_flow,
        "_build_narrowing_payload",
        lambda **kwargs: {"suggested_terms": ["Actuator"], "suggested_term_diagnostics": None},
    )
    monkeypatch.setattr(
        term_flow,
        "_generate_term_answer",
        lambda **kwargs: {
            "response_state": "normal",
            "response_guidance": None,
            "answer_markdown": "answer",
            "llm_error": None,
        },
    )

    result = term_flow.run_term_flow(
        req=req,
        session=cast(Session, object()),
    )

    assert result == {
        "cluster_payload": {"chapters": []},
        "evidence": {"bullets": []},
        "retrieval_warnings": {"state": "normal"},
        "narrowing_payload": {
            "suggested_terms": ["Actuator"],
            "suggested_term_diagnostics": None,
        },
        "response_state": "normal",
        "response_guidance": None,
        "answer_markdown": "answer",
        "llm_error": None,
    }


def test_build_term_cluster_splits_cluster_payload_and_evidence(
    monkeypatch,
) -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "build_cluster",
        lambda **kwargs: {
            "schema_version": "cluster.v1",
            "chapters": [{"chapter_id": "spring::ch1"}],
            "edges": [],
            "evidence": {"bullets": [{"chapter_id": "spring::ch1"}]},
        },
    )

    result = term_flow._build_term_cluster(
        req=req,
        session=cast(Session, object()),
    )

    assert result == {
        "cluster_payload": {
            "schema_version": "cluster.v1",
            "chapters": [{"chapter_id": "spring::ch1"}],
            "edges": [],
        },
        "evidence": {"bullets": [{"chapter_id": "spring::ch1"}]},
    }


def test_evaluate_term_quality_maps_blocked_state(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "evaluate_term_retrieval_quality",
        lambda **kwargs: {
            "state": "broad_blocked",
            "term_too_broad": True,
        },
    )

    result = term_flow._evaluate_term_quality(
        req=req,
        cluster_result={
            "cluster_payload": {"seed": {"seed_chapter_ids": ["a", "b", "c", "d", "e"]}},
            "evidence": {"bullets": []},
        },
    )

    assert result == {
        "retrieval_warnings": {
            "state": "broad_blocked",
            "term_too_broad": True,
        },
        "response_state": "needs_narrower_term",
    }


def test_build_narrowing_payload_reranks_blocked_candidates(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "recommend_narrower_terms",
        lambda **kwargs: {
            "reason": "spring_persistence",
            "suggested_terms": [
                "Spring Data",
                "data persistence",
                "JdbcTemplate",
            ],
            "source": "rule_based",
            "confidence": "heuristic",
        },
    )
    monkeypatch.setattr(
        term_flow,
        "rank_candidate_anchors",
        lambda **kwargs: [
            {"term": "data persistence"},
            {"term": "JdbcTemplate"},
            {"term": "Spring Data"},
        ],
    )

    quality_result = {
        "retrieval_warnings": {
            "state": "broad_blocked",
            "term_too_broad": True,
        },
        "response_state": "needs_narrower_term",
    }

    result = term_flow._build_narrowing_payload(
        req=req,
        session=cast(Session, object()),
        cluster_result={},
        quality_result=quality_result,
    )

    assert result == {
        "suggested_terms": [
            "data persistence",
            "JdbcTemplate",
            "Spring Data",
        ],
        "suggested_term_diagnostics": [
            {"term": "data persistence"},
            {"term": "JdbcTemplate"},
            {"term": "Spring Data"},
        ],
        "recommendation_reason": "spring_persistence",
        "recommendation_source": "rule_based",
        "recommendation_confidence": "heuristic",
    }
    assert quality_result["retrieval_warnings"] == {
        "state": "broad_blocked",
        "term_too_broad": True,
        "suggested_terms": [
            "data persistence",
            "JdbcTemplate",
            "Spring Data",
        ],
        "suggested_term_diagnostics": [
            {"term": "data persistence"},
            {"term": "JdbcTemplate"},
            {"term": "Spring Data"},
        ],
        "recommendation_reason": "spring_persistence",
        "recommendation_source": "rule_based",
        "recommendation_confidence": "heuristic",
    }


def test_build_narrowing_payload_keeps_rule_order_when_rerank_fails(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "recommend_narrower_terms",
        lambda **kwargs: {
            "reason": "spring_persistence",
            "suggested_terms": [
                "Spring Data",
                "data persistence",
                "JdbcTemplate",
            ],
            "source": "rule_based",
            "confidence": "heuristic",
        },
    )
    monkeypatch.setattr(
        term_flow,
        "rank_candidate_anchors",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("probe failed")),
    )

    quality_result = {
        "retrieval_warnings": {
            "state": "broad_blocked",
            "term_too_broad": True,
        },
        "response_state": "needs_narrower_term",
    }

    result = term_flow._build_narrowing_payload(
        req=req,
        session=cast(Session, object()),
        cluster_result={},
        quality_result=quality_result,
    )

    assert result["suggested_terms"] == [
        "Spring Data",
        "data persistence",
        "JdbcTemplate",
    ]
    assert result["suggested_term_diagnostics"] is None
