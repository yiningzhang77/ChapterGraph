from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.candidate_anchor import rank_candidate_anchors
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    broad_overview_prompt_note,
    default_term_user_query,
    evaluate_term_retrieval_quality,
)
from feature_achievement.ask.term_recommender import recommend_narrower_terms
from feature_achievement.llm.qwen_client import ask_qwen


def run_term_flow(
    *,
    req: AskRequest,
    session: Session,
) -> dict[str, object]:
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
    return {
        "cluster_payload": cluster_result.get("cluster_payload"),
        "evidence": cluster_result.get("evidence"),
        "retrieval_warnings": quality_result.get("retrieval_warnings"),
        "narrowing_payload": narrowing_result,
        "response_state": answer_result.get("response_state"),
        "response_guidance": answer_result.get("response_guidance"),
        "answer_markdown": answer_result.get("answer_markdown"),
        "llm_error": answer_result.get("llm_error"),
    }


def _build_term_cluster(
    *,
    req: AskRequest,
    session: Session,
) -> dict[str, object]:
    cluster = build_cluster(session=session, req=req)
    evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
    cluster_payload = dict(cluster)
    cluster_payload.pop("evidence", None)
    return {
        "cluster_payload": cluster_payload,
        "evidence": evidence,
    }


def _evaluate_term_quality(
    *,
    req: AskRequest,
    cluster_result: dict[str, object],
) -> dict[str, object]:
    cluster_payload = cluster_result.get("cluster_payload")
    evidence = cluster_result.get("evidence")
    if not isinstance(cluster_payload, dict):
        return {
            "retrieval_warnings": None,
            "response_state": None,
        }

    term = req.term or ""
    user_query = req.user_query or default_term_user_query(term)
    default_query = default_term_user_query(term)
    retrieval_warnings = evaluate_term_retrieval_quality(
        term=term,
        user_query=user_query,
        user_query_was_default=user_query == default_query,
        cluster=cluster_payload,
        evidence=evidence if isinstance(evidence, dict) else None,
    )

    response_state: str | None = None
    if isinstance(retrieval_warnings, dict):
        state = retrieval_warnings.get("state")
        if state == "broad_blocked":
            response_state = "needs_narrower_term"
        elif state == "broad_allowed":
            response_state = "broad_overview"

    return {
        "retrieval_warnings": retrieval_warnings,
        "response_state": response_state,
    }


def _build_narrowing_payload(
    *,
    req: AskRequest,
    session: Session,
    cluster_result: dict[str, object],
    quality_result: dict[str, object],
) -> dict[str, object]:
    _ = cluster_result
    retrieval_warnings = quality_result.get("retrieval_warnings")
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
    recommendation = recommend_narrower_terms(
        broad_term=term,
        user_query=user_query,
    )

    suggested_terms: list[str] = []
    raw_suggested_terms = recommendation.get("suggested_terms")
    if isinstance(raw_suggested_terms, list):
        suggested_terms = [
            value for value in raw_suggested_terms if isinstance(value, str)
        ]

    diagnostics: list[dict[str, object]] | None = None
    if retrieval_warnings.get("state") == "broad_blocked" and suggested_terms:
        try:
            ranked_candidates = rank_candidate_anchors(
                terms=suggested_terms,
                user_query=user_query,
                run_id=req.run_id,
                enrichment_version=req.enrichment_version,
                session=session,
            )
        except Exception:
            ranked_candidates = []
        ranked_terms = [
            candidate.get("term")
            for candidate in ranked_candidates
            if isinstance(candidate, dict)
            and isinstance(candidate.get("term"), str)
        ]
        if ranked_terms:
            suggested_terms = ranked_terms
        if ranked_candidates:
            diagnostics = ranked_candidates

    retrieval_warnings["suggested_terms"] = suggested_terms
    if diagnostics is not None:
        retrieval_warnings["suggested_term_diagnostics"] = diagnostics

    recommendation_reason = recommendation.get("reason")
    if isinstance(recommendation_reason, str):
        retrieval_warnings["recommendation_reason"] = recommendation_reason

    recommendation_source = recommendation.get("source")
    if isinstance(recommendation_source, str):
        retrieval_warnings["recommendation_source"] = recommendation_source

    recommendation_confidence = recommendation.get("confidence")
    if isinstance(recommendation_confidence, str):
        retrieval_warnings["recommendation_confidence"] = recommendation_confidence

    return {
        "suggested_terms": suggested_terms,
        "suggested_term_diagnostics": diagnostics,
        "recommendation_reason": recommendation_reason
        if isinstance(recommendation_reason, str)
        else None,
        "recommendation_source": recommendation_source
        if isinstance(recommendation_source, str)
        else None,
        "recommendation_confidence": recommendation_confidence
        if isinstance(recommendation_confidence, str)
        else None,
    }


def _generate_term_answer(
    *,
    req: AskRequest,
    cluster_result: dict[str, object],
    quality_result: dict[str, object],
    narrowing_result: dict[str, object],
) -> dict[str, object]:
    cluster_payload = cluster_result.get("cluster_payload")
    retrieval_warnings = quality_result.get("retrieval_warnings")
    if not isinstance(cluster_payload, dict):
        return {
            "response_state": None,
            "response_guidance": None,
            "answer_markdown": None,
            "llm_error": None,
        }

    response_state = (
        quality_result.get("response_state")
        if isinstance(quality_result.get("response_state"), str)
        else None
    )
    suggested_terms = narrowing_result.get("suggested_terms")
    response_guidance: str | None = None
    if response_state == "broad_overview":
        response_guidance = broad_overview_prompt_note(
            suggested_terms if isinstance(suggested_terms, list) else []
        )

    answer_markdown: str | None = None
    llm_error: str | None = None
    if req.llm_enabled and response_state != "needs_narrower_term":
        try:
            answer_markdown = ask_qwen(
                query=req.user_query or default_term_user_query(req.term or ""),
                query_type=req.query_type,
                cluster=cluster_payload,
                retrieval_term=req.term,
                response_guidance=response_guidance,
                model=req.llm_model,
                timeout_ms=req.llm_timeout_ms,
            )
        except Exception as error:
            llm_error = str(error)

    return {
        "response_state": response_state,
        "response_guidance": response_guidance,
        "answer_markdown": answer_markdown,
        "llm_error": llm_error,
    }
