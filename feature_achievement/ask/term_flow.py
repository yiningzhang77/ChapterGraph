from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    default_term_user_query,
    evaluate_term_retrieval_quality,
)


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
        "response_state": quality_result.get("response_state")
        if quality_result.get("response_state") is not None
        else answer_result.get("response_state"),
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
    _ = (req, session, cluster_result, quality_result)
    return {
        "suggested_terms": None,
        "suggested_term_diagnostics": None,
    }


def _generate_term_answer(
    *,
    req: AskRequest,
    cluster_result: dict[str, object],
    quality_result: dict[str, object],
    narrowing_result: dict[str, object],
) -> dict[str, object]:
    _ = (req, cluster_result, quality_result, narrowing_result)
    return {
        "response_state": None,
        "response_guidance": None,
        "answer_markdown": None,
        "llm_error": None,
    }
