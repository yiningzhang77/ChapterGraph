from __future__ import annotations

from feature_achievement.ask.runtime_contracts import (
    RuntimeExecutionStatus,
    RuntimeResult,
)
from feature_achievement.ask.tool_contracts import (
    RUNTIME_STATE_NEEDS_NARROWER_TERM,
    ChapterFlowResult,
    TermFlowResult,
)

__all__ = [
    "chapter_flow_result_to_runtime_result",
    "term_flow_result_to_runtime_result",
]


def term_flow_result_to_runtime_result(
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


def chapter_flow_result_to_runtime_result(
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
