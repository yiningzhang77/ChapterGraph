from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest


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
    _ = (req, session)
    return {
        "cluster_payload": None,
        "evidence": None,
    }


def _evaluate_term_quality(
    *,
    req: AskRequest,
    cluster_result: dict[str, object],
) -> dict[str, object]:
    _ = (req, cluster_result)
    return {
        "retrieval_warnings": None,
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
