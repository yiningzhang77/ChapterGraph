from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import term_tools
from feature_achievement.ask.tool_contracts import (
    CandidateAnchorDiagnostic,
    CandidateAnchorRankingToolResult,
    ClusterToolResult,
    NarrowingRecommendationToolResult,
    RetrievalQualityToolResult,
    TermAnswerToolResult,
)


def test_build_term_cluster_tool_returns_typed_contract(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_tools,
        "build_cluster",
        lambda **kwargs: {
            "schema_version": "cluster.v1",
            "seed": {"seed_chapter_ids": ["spring::ch1"]},
            "chapters": [{"chapter_id": "spring::ch1"}],
            "edges": [],
            "evidence": {"bullets": [{"chapter_id": "spring::ch1"}]},
        },
    )

    result = term_tools.build_term_cluster_tool(
        req=req,
        session=cast(Session, object()),
    )

    assert result == ClusterToolResult(
        term="Actuator",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        cluster={
            "schema_version": "cluster.v1",
            "seed": {"seed_chapter_ids": ["spring::ch1"]},
            "chapters": [{"chapter_id": "spring::ch1"}],
            "edges": [],
        },
        evidence={"bullets": [{"chapter_id": "spring::ch1"}]},
        seed_ids=["spring::ch1"],
    )


def test_evaluate_term_retrieval_quality_tool_returns_typed_state(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="What is Spring?",
        run_id=5,
        llm_enabled=False,
    )
    cluster_result = ClusterToolResult(
        term="Spring",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        cluster={"chapters": [], "seed": {"seed_chapter_ids": ["a", "b", "c", "d", "e"]}},
        evidence={"bullets": []},
        seed_ids=["a", "b", "c", "d", "e"],
    )

    monkeypatch.setattr(
        term_tools,
        "evaluate_term_retrieval_quality",
        lambda **kwargs: {"state": "broad_allowed", "term_too_broad": True},
    )

    result = term_tools.evaluate_term_retrieval_quality_tool(
        req=req,
        cluster_result=cluster_result,
    )

    assert result == RetrievalQualityToolResult(
        state="broad_allowed",
        retrieval_warnings={"state": "broad_allowed", "term_too_broad": True},
        response_guidance=None,
    )


def test_recommend_narrower_terms_tool_preserves_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        term_tools,
        "recommend_narrower_terms",
        lambda **kwargs: {
            "suggested_terms": ["JdbcTemplate", "Spring Data JPA"],
            "reason": "spring_persistence",
            "source": "rule_based",
            "confidence": "heuristic",
        },
    )

    result = term_tools.recommend_narrower_terms_tool(
        term="Spring",
        user_query="How does Spring implement data persistence?",
    )

    assert result == NarrowingRecommendationToolResult(
        suggested_terms=["JdbcTemplate", "Spring Data JPA"],
        recommendation_reason="spring_persistence",
        recommendation_source="rule_based",
        recommendation_confidence="heuristic",
    )


def test_rank_candidate_anchors_tool_preserves_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(
        term_tools,
        "rank_candidate_anchors",
        lambda **kwargs: [
            {
                "term": "JdbcTemplate",
                "focus_state": "focused",
                "expected_response_state": "normal",
                "seed_count": 2,
                "evidence_chapter_count": 2,
                "evidence_book_count": 1,
                "source": "retrieval_probe",
            },
            {
                "term": "Spring Data",
                "focus_state": "broad",
                "expected_response_state": "needs_narrower_term",
                "seed_count": 5,
                "evidence_chapter_count": 5,
                "evidence_book_count": 3,
                "source": "retrieval_probe",
            },
        ],
    )

    result = term_tools.rank_candidate_anchors_tool(
        candidates=["Spring Data", "JdbcTemplate"],
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result == CandidateAnchorRankingToolResult(
        suggested_terms=["JdbcTemplate", "Spring Data"],
        diagnostics=[
            CandidateAnchorDiagnostic(
                term="JdbcTemplate",
                focus_state="focused",
                expected_response_state="normal",
                seed_count=2,
                evidence_chapter_count=2,
                evidence_book_count=1,
                source="retrieval_probe",
            ),
            CandidateAnchorDiagnostic(
                term="Spring Data",
                focus_state="broad",
                expected_response_state="needs_narrower_term",
                seed_count=5,
                evidence_chapter_count=5,
                evidence_book_count=3,
                source="retrieval_probe",
            ),
        ],
    )


def test_generate_term_answer_tool_returns_typed_answer_result(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_ask_qwen(**kwargs: object) -> str:
        captured.update(kwargs)
        return "answer ok"

    monkeypatch.setattr(term_tools, "ask_qwen", fake_ask_qwen)

    result = term_tools.generate_term_answer_tool(
        term="Actuator",
        user_query="Tell me about Actuator",
        cluster={"chapters": []},
        response_mode="normal",
        response_guidance=None,
        llm_enabled=True,
        llm_model=None,
        llm_timeout_ms=30000,
    )

    assert result == TermAnswerToolResult(
        answer_markdown="answer ok",
        llm_error=None,
    )
    assert captured["query_type"] == "term"
    assert captured["retrieval_term"] == "Actuator"


def test_generate_term_answer_tool_returns_typed_error_result(monkeypatch) -> None:
    monkeypatch.setattr(
        term_tools,
        "ask_qwen",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("llm failure")),
    )

    result = term_tools.generate_term_answer_tool(
        term="Actuator",
        user_query="Tell me about Actuator",
        cluster={"chapters": []},
        response_mode="normal",
        response_guidance=None,
        llm_enabled=True,
        llm_model=None,
        llm_timeout_ms=30000,
    )

    assert result == TermAnswerToolResult(
        answer_markdown=None,
        llm_error="llm failure",
    )
