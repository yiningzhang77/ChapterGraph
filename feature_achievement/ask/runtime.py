from __future__ import annotations

"""Deterministic runtime shell for /ask execution."""

from uuid import uuid4

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.chapter_flow import run_chapter_flow
from feature_achievement.ask.runtime_contracts import (
    RuntimeExecutionStatus,
    RuntimeRequest,
    RuntimeResult,
)
from feature_achievement.ask.term_flow import run_term_flow
from feature_achievement.ask.tool_contracts import (
    RUNTIME_STATE_NEEDS_NARROWER_TERM,
    ChapterFlowResult,
    TermFlowResult,
)

__all__ = ["run_runtime"]


def run_runtime(*, request: RuntimeRequest, session: Session) -> RuntimeResult:
    execution_id = f"runtime-{uuid4().hex}"
    ask_request = _to_ask_request(request)
    if request.query_type == "term":
        flow_result = run_term_flow(req=ask_request, session=session)
        return _term_flow_result_to_runtime_result(
            flow_result=flow_result,
            execution_id=execution_id,
        )

    flow_result = run_chapter_flow(req=ask_request, session=session)
    return _chapter_flow_result_to_runtime_result(
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


def _term_flow_result_to_runtime_result(
    *,
    flow_result: TermFlowResult,
    execution_id: str,
) -> RuntimeResult:
    return RuntimeResult(
        execution_id=execution_id,
        status=_execution_status_from_runtime_state(flow_result.runtime_state),
        final_state={
            "cluster_payload": flow_result.cluster_payload,
            "evidence": flow_result.evidence,
            "retrieval_warnings": flow_result.retrieval_warnings,
            "response_guidance": flow_result.response_guidance,
            "llm_error": flow_result.llm_error,
        },
        answer_markdown=flow_result.answer_markdown,
        runtime_state=flow_result.runtime_state,
        events=[
            {
                "type": "term_flow_completed",
                "runtime_state": flow_result.runtime_state,
            }
        ],
        error_message=None,
    )


def _chapter_flow_result_to_runtime_result(
    *,
    flow_result: ChapterFlowResult,
    execution_id: str,
) -> RuntimeResult:
    return RuntimeResult(
        execution_id=execution_id,
        status=_execution_status_from_runtime_state(flow_result.runtime_state),
        final_state={
            "cluster_payload": flow_result.cluster_payload,
            "evidence": flow_result.evidence,
            "retrieval_warnings": flow_result.retrieval_warnings,
            "response_guidance": flow_result.response_guidance,
            "llm_error": flow_result.llm_error,
        },
        answer_markdown=flow_result.answer_markdown,
        runtime_state=flow_result.runtime_state,
        events=[
            {
                "type": "chapter_flow_completed",
                "runtime_state": flow_result.runtime_state,
            }
        ],
        error_message=None,
    )


def _execution_status_from_runtime_state(runtime_state: str) -> RuntimeExecutionStatus:
    if runtime_state == RUNTIME_STATE_NEEDS_NARROWER_TERM:
        return "blocked"
    return "completed"
