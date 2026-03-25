from feature_achievement.ask.runtime_contracts import (
    PlannerDecision,
    RuntimeRequest,
    RuntimeResult,
    RuntimeStepInput,
    RuntimeStepResult,
)


def test_runtime_request_fields_are_explicit() -> None:
    request = RuntimeRequest(
        query_type="term",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        max_hops=2,
        seed_top_k=5,
        neighbor_top_k=40,
        section_top_k=10,
        bullet_top_k=20,
        min_edge_score=0.2,
        llm_enabled=True,
        llm_model="qwen",
        llm_timeout_ms=60_000,
        term="Actuator",
        user_query="Tell me about Actuator",
        chapter_id=None,
        query=None,
        return_cluster=True,
        return_graph_fragment=False,
    )

    assert request.query_type == "term"
    assert request.term == "Actuator"
    assert request.chapter_id is None
    assert request.max_hops == 2


def test_runtime_step_and_execution_results_capture_status_and_payloads() -> None:
    request = RuntimeRequest(
        query_type="chapter",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        max_hops=2,
        seed_top_k=5,
        neighbor_top_k=40,
        section_top_k=10,
        bullet_top_k=20,
        min_edge_score=0.2,
        llm_enabled=False,
        llm_model=None,
        llm_timeout_ms=60_000,
        term=None,
        user_query=None,
        chapter_id="spring::ch2",
        query="Summarize the chapter",
        return_cluster=False,
        return_graph_fragment=False,
    )
    step_input = RuntimeStepInput(
        request=request,
        execution_id="exec-1",
        step_id="build_chapter_cluster",
        state={"runtime_state": "normal"},
    )
    step_result = RuntimeStepResult(
        step_id="build_chapter_cluster",
        status="completed",
        state_patch={"cluster_result": {"chapter_id": "spring::ch2"}},
        emitted_events=[{"type": "cluster_built"}],
        blocking_reason=None,
        error_message=None,
    )
    runtime_result = RuntimeResult(
        execution_id="exec-1",
        status="completed",
        final_state={"answer_result": "done"},
        answer_markdown="answer",
        runtime_state="normal",
        events=[{"type": "finished"}],
        error_message=None,
    )

    assert step_input.execution_id == "exec-1"
    assert step_result.status == "completed"
    assert runtime_result.runtime_state == "normal"


def test_planner_decision_is_structured() -> None:
    decision = PlannerDecision(
        action_type="call_tool",
        target_name="build_term_cluster_tool",
        input_patch={"term": "Actuator"},
        reason="term query requires retrieval first",
    )

    assert decision.action_type == "call_tool"
    assert decision.target_name == "build_term_cluster_tool"
