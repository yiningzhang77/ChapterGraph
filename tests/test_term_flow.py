from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import term_flow
from feature_achievement.ask.tool_contracts import (
    CandidateAnchorDiagnostic,
    CandidateAnchorRankingToolResult,
    ClusterToolResult,
    NarrowingRecommendationToolResult,
    RetrievalQualityToolResult,
    TermAnswerToolResult,
    TermFlowResult,
)


def _cluster_result() -> ClusterToolResult:
    return ClusterToolResult(
        term="Actuator",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        cluster={"chapters": [], "edges": [], "seed": {"seed_chapter_ids": ["spring::ch1"]}},
        evidence={"bullets": []},
        seed_ids=["spring::ch1"],
    )


def test_run_term_flow_returns_service_shape(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(term_flow, "_build_term_cluster", lambda **kwargs: _cluster_result())
    monkeypatch.setattr(
        term_flow,
        "_evaluate_term_quality",
        lambda **kwargs: RetrievalQualityToolResult(
            state=None,
            retrieval_warnings={"state": "normal"},
            response_guidance=None,
        ),
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
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": "answer",
            "llm_error": None,
        },
    )

    result = term_flow.run_term_flow(
        req=req,
        session=cast(Session, object()),
    )

    assert result == TermFlowResult(
        cluster_payload={
            "chapters": [],
            "edges": [],
            "seed": {"seed_chapter_ids": ["spring::ch1"]},
        },
        evidence={"bullets": []},
        retrieval_warnings={"state": "normal"},
        response_state=None,
        response_guidance=None,
        answer_markdown="answer",
        llm_error=None,
    )


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
        "recommend_narrower_terms_tool",
        lambda **kwargs: NarrowingRecommendationToolResult(
            suggested_terms=["Spring Data", "data persistence", "JdbcTemplate"],
            recommendation_reason="spring_persistence",
            recommendation_source="rule_based",
            recommendation_confidence="heuristic",
        ),
    )
    monkeypatch.setattr(
        term_flow,
        "rank_candidate_anchors_tool",
        lambda **kwargs: CandidateAnchorRankingToolResult(
            suggested_terms=["data persistence", "JdbcTemplate", "Spring Data"],
            diagnostics=[
                CandidateAnchorDiagnostic(
                    term="data persistence",
                    focus_state="focused",
                    expected_response_state="normal",
                    seed_count=2,
                    evidence_chapter_count=2,
                    evidence_book_count=1,
                    source="retrieval_probe",
                ),
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
        ),
    )

    quality_result = RetrievalQualityToolResult(
        state="broad_blocked",
        retrieval_warnings={"state": "broad_blocked", "term_too_broad": True},
        response_guidance=None,
    )

    result = term_flow._build_narrowing_payload(
        req=req,
        session=cast(Session, object()),
        cluster_result=_cluster_result(),
        quality_result=quality_result,
    )

    assert result == {
        "suggested_terms": [
            "data persistence",
            "JdbcTemplate",
            "Spring Data",
        ],
        "suggested_term_diagnostics": [
            {
                "term": "data persistence",
                "focus_state": "focused",
                "expected_response_state": "normal",
                "seed_count": 2,
                "evidence_chapter_count": 2,
                "evidence_book_count": 1,
                "source": "retrieval_probe",
            },
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
        "recommendation_reason": "spring_persistence",
        "recommendation_source": "rule_based",
        "recommendation_confidence": "heuristic",
    }
    assert quality_result.retrieval_warnings == {
        "state": "broad_blocked",
        "term_too_broad": True,
        "suggested_terms": [
            "data persistence",
            "JdbcTemplate",
            "Spring Data",
        ],
        "suggested_term_diagnostics": [
            {
                "term": "data persistence",
                "focus_state": "focused",
                "expected_response_state": "normal",
                "seed_count": 2,
                "evidence_chapter_count": 2,
                "evidence_book_count": 1,
                "source": "retrieval_probe",
            },
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
        "recommendation_reason": "spring_persistence",
        "recommendation_source": "rule_based",
        "recommendation_confidence": "heuristic",
    }


def test_generate_term_answer_skips_llm_for_blocked_state() -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        llm_enabled=True,
    )

    result = term_flow._generate_term_answer(
        req=req,
        cluster_result=_cluster_result(),
        quality_result=RetrievalQualityToolResult(
            state="broad_blocked",
            retrieval_warnings={"state": "broad_blocked"},
            response_guidance=None,
        ),
        narrowing_result={"suggested_terms": ["JdbcTemplate"]},
    )

    assert result == {
        "response_state": "needs_narrower_term",
        "response_guidance": None,
        "answer_markdown": None,
        "llm_error": None,
    }


def test_generate_term_answer_uses_wrapper_for_overview_state(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="What is Spring?",
        run_id=5,
        llm_enabled=True,
    )
    captured: dict[str, object] = {}

    def fake_answer_tool(**kwargs: object) -> TermAnswerToolResult:
        captured.update(kwargs)
        return TermAnswerToolResult(
            answer_markdown="overview",
            llm_error=None,
        )

    monkeypatch.setattr(term_flow, "generate_term_answer_tool", fake_answer_tool)

    result = term_flow._generate_term_answer(
        req=req,
        cluster_result=_cluster_result(),
        quality_result=RetrievalQualityToolResult(
            state="broad_allowed",
            retrieval_warnings={"state": "broad_allowed"},
            response_guidance=None,
        ),
        narrowing_result={"suggested_terms": ["Spring Data", "JdbcTemplate"]},
    )

    assert result["response_state"] == "broad_overview"
    assert result["answer_markdown"] == "overview"
    assert "high-level concept explanation" in str(result["response_guidance"])
    assert captured["response_mode"] == "overview"


def test_run_term_flow_preserves_broad_overview_state(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="What is Spring?",
        run_id=5,
        llm_enabled=True,
    )

    monkeypatch.setattr(term_flow, "_build_term_cluster", lambda **kwargs: _cluster_result())
    monkeypatch.setattr(
        term_flow,
        "_evaluate_term_quality",
        lambda **kwargs: RetrievalQualityToolResult(
            state="broad_allowed",
            retrieval_warnings={"state": "broad_allowed"},
            response_guidance=None,
        ),
    )
    monkeypatch.setattr(
        term_flow,
        "_build_narrowing_payload",
        lambda **kwargs: {"suggested_terms": ["Spring Data"], "suggested_term_diagnostics": None},
    )
    monkeypatch.setattr(
        term_flow,
        "_generate_term_answer",
        lambda **kwargs: {
            "response_state": "broad_overview",
            "response_guidance": "overview guidance",
            "answer_markdown": "overview answer",
            "llm_error": None,
        },
    )

    result = term_flow.run_term_flow(req=req, session=cast(Session, object()))

    assert result.response_state == "broad_overview"
    assert result.answer_markdown == "overview answer"


def test_run_term_flow_preserves_blocked_state(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Spring",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(term_flow, "_build_term_cluster", lambda **kwargs: _cluster_result())
    monkeypatch.setattr(
        term_flow,
        "_evaluate_term_quality",
        lambda **kwargs: RetrievalQualityToolResult(
            state="broad_blocked",
            retrieval_warnings={"state": "broad_blocked"},
            response_guidance=None,
        ),
    )
    monkeypatch.setattr(
        term_flow,
        "_build_narrowing_payload",
        lambda **kwargs: {"suggested_terms": ["JdbcTemplate"], "suggested_term_diagnostics": None},
    )
    monkeypatch.setattr(
        term_flow,
        "_generate_term_answer",
        lambda **kwargs: {
            "response_state": "needs_narrower_term",
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        },
    )

    result = term_flow.run_term_flow(req=req, session=cast(Session, object()))

    assert result.response_state == "needs_narrower_term"
    assert result.answer_markdown is None
