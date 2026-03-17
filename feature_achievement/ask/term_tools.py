from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.candidate_anchor import rank_candidate_anchors
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    default_term_user_query,
    evaluate_term_retrieval_quality,
)
from feature_achievement.ask.term_recommender import recommend_narrower_terms
from feature_achievement.ask.tool_contracts import (
    CandidateAnchorDiagnostic,
    CandidateAnchorRankingToolResult,
    ClusterToolResult,
    NarrowingRecommendationToolResult,
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


def recommend_narrower_terms_tool(
    *,
    term: str,
    user_query: str | None,
) -> NarrowingRecommendationToolResult:
    effective_user_query = user_query or default_term_user_query(term)
    recommendation = recommend_narrower_terms(
        broad_term=term,
        user_query=effective_user_query,
    )
    suggested_terms = recommendation.get("suggested_terms")
    return NarrowingRecommendationToolResult(
        suggested_terms=[
            suggested_term
            for suggested_term in suggested_terms
            if isinstance(suggested_term, str)
        ] if isinstance(suggested_terms, list) else [],
        recommendation_reason=recommendation.get("reason")
        if isinstance(recommendation.get("reason"), str)
        else None,
        recommendation_source=recommendation.get("source")
        if isinstance(recommendation.get("source"), str)
        else None,
        recommendation_confidence=recommendation.get("confidence")
        if isinstance(recommendation.get("confidence"), str)
        else None,
    )


def rank_candidate_anchors_tool(
    *,
    candidates: list[str],
    user_query: str | None,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> CandidateAnchorRankingToolResult:
    effective_user_query = user_query or ""
    ranked_candidates = rank_candidate_anchors(
        terms=candidates,
        user_query=effective_user_query,
        run_id=run_id,
        enrichment_version=enrichment_version,
        session=session,
    )
    diagnostics = [
        CandidateAnchorDiagnostic(
            term=candidate.get("term") if isinstance(candidate.get("term"), str) else "",
            focus_state=candidate.get("focus_state")
            if isinstance(candidate.get("focus_state"), str)
            else "",
            expected_response_state=candidate.get("expected_response_state")
            if isinstance(candidate.get("expected_response_state"), str)
            else "",
            seed_count=candidate.get("seed_count")
            if isinstance(candidate.get("seed_count"), int)
            else 0,
            evidence_chapter_count=candidate.get("evidence_chapter_count")
            if isinstance(candidate.get("evidence_chapter_count"), int)
            else 0,
            evidence_book_count=candidate.get("evidence_book_count")
            if isinstance(candidate.get("evidence_book_count"), int)
            else 0,
            source=candidate.get("source")
            if isinstance(candidate.get("source"), str)
            else "",
        )
        for candidate in ranked_candidates
        if isinstance(candidate, dict)
    ]
    return CandidateAnchorRankingToolResult(
        suggested_terms=[
            diagnostic.term for diagnostic in diagnostics if diagnostic.term
        ],
        diagnostics=diagnostics,
    )


def _seed_ids_from_cluster(cluster: dict[str, object]) -> list[str]:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return []
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return []
    return [seed_id for seed_id in seed_ids if isinstance(seed_id, str)]
