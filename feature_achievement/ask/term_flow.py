from __future__ import annotations

"""Runtime-callable term flow entrypoint for /ask orchestration."""

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.retrieval_quality import (
    broad_overview_prompt_note,
    default_term_user_query,
)
from feature_achievement.ask.tools import (
    build_term_cluster_tool,
    evaluate_term_retrieval_quality_tool,
    generate_term_answer_tool,
    rank_candidate_anchors_tool,
    recommend_narrower_terms_tool,
)
from feature_achievement.ask.tool_contracts import (
    ClusterToolResult,
    NarrowingRecommendationToolResult,
    RUNTIME_STATE_BROAD_OVERVIEW,
    RUNTIME_STATE_NEEDS_NARROWER_TERM,
    RUNTIME_STATE_NORMAL,
    RetrievalQualityToolResult,
    TermFlowResult,
)

__all__ = ["run_term_flow"]


def run_term_flow(
    *,
    req: AskRequest,
    session: Session,
) -> TermFlowResult:
    cluster_result = _build_term_cluster(req=req, session=session)
    quality_result = _evaluate_term_quality(req=req, cluster_result=cluster_result)
    narrowing_result = _build_narrowing_payload(
        req=req,
        session=session,
        cluster_result=cluster_result,
        quality_result=quality_result,
    )
    answer_result = _generate_term_answer(
        req=req,
        cluster_result=cluster_result,
        quality_result=quality_result,
        narrowing_result=narrowing_result,
    )
    return TermFlowResult(
        cluster_payload=cluster_result.cluster,
        evidence=cluster_result.evidence,
        retrieval_warnings=quality_result.retrieval_warnings,
        runtime_state=answer_result["runtime_state"],
        response_guidance=answer_result["response_guidance"],
        answer_markdown=answer_result["answer_markdown"],
        llm_error=answer_result["llm_error"],
    )


def _build_term_cluster(
    *,
    req: AskRequest,
    session: Session,
) -> ClusterToolResult:
    return build_term_cluster_tool(req=req, session=session)


def _evaluate_term_quality(
    *,
    req: AskRequest,
    cluster_result: ClusterToolResult,
) -> RetrievalQualityToolResult:
    return evaluate_term_retrieval_quality_tool(
        req=req,
        cluster_result=cluster_result,
    )


def _build_narrowing_payload(
    *,
    req: AskRequest,
    session: Session,
    cluster_result: ClusterToolResult,
    quality_result: RetrievalQualityToolResult,
) -> dict[str, object]:
    _ = cluster_result
    retrieval_warnings = quality_result.retrieval_warnings
    if not isinstance(retrieval_warnings, dict):
        return {
            "suggested_terms": None,
            "suggested_term_diagnostics": None,
            "recommendation_reason": None,
            "recommendation_source": None,
            "recommendation_confidence": None,
        }

    term = req.term or ""
    user_query = req.user_query or default_term_user_query(term)
    recommendation = recommend_narrower_terms_tool(
        term=term,
        user_query=user_query,
    )

    suggested_terms = list(recommendation.suggested_terms)

    diagnostics: list[dict[str, object]] | None = None
    if retrieval_warnings.get("state") == "broad_blocked" and suggested_terms:
        try:
            ranking_result = rank_candidate_anchors_tool(
                candidates=suggested_terms,
                user_query=user_query,
                run_id=req.run_id,
                enrichment_version=req.enrichment_version,
                session=session,
            )
        except Exception:
            ranking_result = None
        if ranking_result is not None:
            if ranking_result.suggested_terms:
                suggested_terms = list(ranking_result.suggested_terms)
            if ranking_result.diagnostics:
                diagnostics = [
                    {
                        "term": diagnostic.term,
                        "focus_state": diagnostic.focus_state,
                        "expected_response_state": diagnostic.expected_response_state,
                        "seed_count": diagnostic.seed_count,
                        "evidence_chapter_count": diagnostic.evidence_chapter_count,
                        "evidence_book_count": diagnostic.evidence_book_count,
                        "source": diagnostic.source,
                    }
                    for diagnostic in ranking_result.diagnostics
                ]

    retrieval_warnings["suggested_terms"] = suggested_terms
    if diagnostics is not None:
        retrieval_warnings["suggested_term_diagnostics"] = diagnostics

    recommendation_reason = recommendation.recommendation_reason
    if recommendation_reason is not None:
        retrieval_warnings["recommendation_reason"] = recommendation_reason

    recommendation_source = recommendation.recommendation_source
    if recommendation_source is not None:
        retrieval_warnings["recommendation_source"] = recommendation_source

    recommendation_confidence = recommendation.recommendation_confidence
    if recommendation_confidence is not None:
        retrieval_warnings["recommendation_confidence"] = recommendation_confidence

    return {
        "suggested_terms": suggested_terms,
        "suggested_term_diagnostics": diagnostics,
        "recommendation_reason": recommendation_reason,
        "recommendation_source": recommendation_source,
        "recommendation_confidence": recommendation_confidence,
    }


def _generate_term_answer(
    *,
    req: AskRequest,
    cluster_result: ClusterToolResult,
    quality_result: RetrievalQualityToolResult,
    narrowing_result: dict[str, object],
) -> dict[str, object]:
    retrieval_warnings = quality_result.retrieval_warnings
    runtime_state = _runtime_state_from_quality(quality_result.state)
    suggested_terms = narrowing_result.get("suggested_terms")
    response_guidance: str | None = None
    if runtime_state == RUNTIME_STATE_BROAD_OVERVIEW:
        response_guidance = broad_overview_prompt_note(
            suggested_terms if isinstance(suggested_terms, list) else []
        )

    answer_markdown: str | None = None
    llm_error: str | None = None
    if req.llm_enabled and runtime_state != RUNTIME_STATE_NEEDS_NARROWER_TERM:
        answer_result = generate_term_answer_tool(
            term=req.term or "",
            user_query=req.user_query,
            cluster=cluster_result.cluster,
            response_mode="overview"
            if runtime_state == RUNTIME_STATE_BROAD_OVERVIEW
            else "normal",
            response_guidance=response_guidance,
            llm_enabled=req.llm_enabled,
            llm_model=req.llm_model,
            llm_timeout_ms=req.llm_timeout_ms,
        )
        answer_markdown = answer_result.answer_markdown
        llm_error = answer_result.llm_error

    return {
        "runtime_state": runtime_state,
        "response_guidance": response_guidance,
        "answer_markdown": answer_markdown,
        "llm_error": llm_error,
    }


def _runtime_state_from_quality(state: str | None) -> str:
    if state == "broad_blocked":
        return RUNTIME_STATE_NEEDS_NARROWER_TERM
    if state == "broad_allowed":
        return RUNTIME_STATE_BROAD_OVERVIEW
    return RUNTIME_STATE_NORMAL
