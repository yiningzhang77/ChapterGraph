from __future__ import annotations

from feature_achievement.ask.runtime_result_adapter import (
    chapter_flow_result_to_runtime_result,
    term_flow_result_to_runtime_result,
)
from feature_achievement.ask.tool_contracts import (
    ChapterFlowResult,
    RUNTIME_STATE_NEEDS_NARROWER_TERM,
    RUNTIME_STATE_NORMAL,
    TermFlowResult,
)


def test_term_flow_result_to_runtime_result_maps_blocked_state() -> None:
    runtime_result = term_flow_result_to_runtime_result(
        flow_result=TermFlowResult(
            cluster_payload={"schema_version": "cluster.v1"},
            evidence={"sections": [], "bullets": []},
            retrieval_warnings={"state": "broad_blocked"},
            runtime_state=RUNTIME_STATE_NEEDS_NARROWER_TERM,
            response_guidance=None,
            answer_markdown=None,
            llm_error=None,
        ),
        execution_id="runtime-1",
    )

    assert runtime_result.execution_id == "runtime-1"
    assert runtime_result.status == "blocked"
    assert runtime_result.final_state["retrieval_warnings"] == {
        "state": "broad_blocked"
    }
    assert runtime_result.events == [
        {
            "type": "term_flow_completed",
            "runtime_state": RUNTIME_STATE_NEEDS_NARROWER_TERM,
        }
    ]


def test_chapter_flow_result_to_runtime_result_maps_completed_state() -> None:
    runtime_result = chapter_flow_result_to_runtime_result(
        flow_result=ChapterFlowResult(
            cluster_payload={"schema_version": "cluster.v1"},
            evidence={"sections": [], "bullets": []},
            retrieval_warnings=None,
            runtime_state=RUNTIME_STATE_NORMAL,
            response_guidance=None,
            answer_markdown="summary",
            llm_error=None,
        ),
        execution_id="runtime-2",
    )

    assert runtime_result.execution_id == "runtime-2"
    assert runtime_result.status == "completed"
    assert runtime_result.answer_markdown == "summary"
    assert runtime_result.final_state["cluster_payload"] == {
        "schema_version": "cluster.v1"
    }
    assert runtime_result.events == [
        {
            "type": "chapter_flow_completed",
            "runtime_state": RUNTIME_STATE_NORMAL,
        }
    ]
