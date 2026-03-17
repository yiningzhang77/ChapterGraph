from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    default_term_user_query,
    evaluate_term_retrieval_quality,
)
from feature_achievement.ask.tool_contracts import (
    ClusterToolResult,
    RetrievalQualityToolResult,
)


def build_term_cluster_tool(
    *,
    req: AskRequest,
    session: Session,
) -> ClusterToolResult:
    cluster = build_cluster(session=session, req=req)
    evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
    cluster_payload = dict(cluster)
    cluster_payload.pop("evidence", None)
    return ClusterToolResult(
        term=req.term or "",
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        cluster=cluster_payload,
        evidence=evidence,
        seed_ids=_seed_ids_from_cluster(cluster_payload),
    )


def evaluate_term_retrieval_quality_tool(
    *,
    req: AskRequest,
    cluster_result: ClusterToolResult,
) -> RetrievalQualityToolResult:
    term = req.term or ""
    user_query = req.user_query or default_term_user_query(term)
    default_query = default_term_user_query(term)
    retrieval_warnings = evaluate_term_retrieval_quality(
        term=term,
        user_query=user_query,
        user_query_was_default=user_query == default_query,
        cluster=cluster_result.cluster,
        evidence=cluster_result.evidence,
    )
    state = retrieval_warnings.get("state") if isinstance(retrieval_warnings, dict) else None
    if not isinstance(state, str):
        state = None
    return RetrievalQualityToolResult(
        state=state,
        retrieval_warnings=retrieval_warnings,
        response_guidance=None,
    )


def _seed_ids_from_cluster(cluster: dict[str, object]) -> list[str]:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return []
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return []
    return [seed_id for seed_id in seed_ids if isinstance(seed_id, str)]
