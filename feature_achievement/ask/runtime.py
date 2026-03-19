from __future__ import annotations

"""Deterministic runtime shell for /ask execution."""

from uuid import uuid4

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.chapter_flow import run_chapter_flow
from feature_achievement.ask.runtime_contracts import RuntimeRequest, RuntimeResult
from feature_achievement.ask.runtime_result_adapter import (
    chapter_flow_result_to_runtime_result,
    term_flow_result_to_runtime_result,
)
from feature_achievement.ask.term_flow import run_term_flow

__all__ = ["run_runtime"]


def run_runtime(*, request: RuntimeRequest, session: Session) -> RuntimeResult:
    execution_id = f"runtime-{uuid4().hex}"
    ask_request = _to_ask_request(request)
    if request.query_type == "term":
        flow_result = run_term_flow(req=ask_request, session=session)
        return term_flow_result_to_runtime_result(
            flow_result=flow_result,
            execution_id=execution_id,
        )

    flow_result = run_chapter_flow(req=ask_request, session=session)
    return chapter_flow_result_to_runtime_result(
        flow_result=flow_result,
        execution_id=execution_id,
    )


def _to_ask_request(request: RuntimeRequest) -> AskRequest:
    return AskRequest(
        query=request.query,
        term=request.term,
        user_query=request.user_query,
        query_type=request.query_type,
        run_id=request.run_id,
        enrichment_version=request.enrichment_version,
        chapter_id=request.chapter_id,
        max_hops=request.max_hops,
        seed_top_k=request.seed_top_k,
        neighbor_top_k=request.neighbor_top_k,
        section_top_k=request.section_top_k,
        bullet_top_k=request.bullet_top_k,
        min_edge_score=request.min_edge_score,
        llm_enabled=request.llm_enabled,
        llm_model=request.llm_model or "qwen",
        llm_timeout_ms=request.llm_timeout_ms,
        return_cluster=request.return_cluster,
        return_graph_fragment=request.return_graph_fragment,
    )
