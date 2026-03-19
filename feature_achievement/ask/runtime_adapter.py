from __future__ import annotations

"""Thin adapters between API-layer ask models and runtime contracts."""

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.runtime_contracts import RuntimeRequest

__all__ = ["to_runtime_request"]


def to_runtime_request(req: AskRequest) -> RuntimeRequest:
    return RuntimeRequest(
        query_type=req.query_type,
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        max_hops=req.max_hops,
        seed_top_k=req.seed_top_k,
        neighbor_top_k=req.neighbor_top_k,
        section_top_k=req.section_top_k,
        bullet_top_k=req.bullet_top_k,
        min_edge_score=req.min_edge_score,
        llm_enabled=req.llm_enabled,
        llm_model=req.llm_model,
        llm_timeout_ms=req.llm_timeout_ms,
        term=req.term,
        user_query=req.user_query,
        chapter_id=req.chapter_id,
        query=req.query,
        return_cluster=req.return_cluster,
        return_graph_fragment=req.return_graph_fragment,
    )
