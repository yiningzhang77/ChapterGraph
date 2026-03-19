from feature_achievement.ask import (
    chapter_flow,
    runtime,
    runtime_adapter,
    runtime_contracts,
    runtime_surface,
    term_flow,
    tools,
)


def test_runtime_surface_exports_flow_entrypoints() -> None:
    assert runtime_surface.run_term_flow is term_flow.run_term_flow
    assert runtime_surface.run_chapter_flow is chapter_flow.run_chapter_flow
    assert runtime_surface.run_runtime is runtime.run_runtime


def test_runtime_surface_exports_tool_entrypoints() -> None:
    assert runtime_surface.build_term_cluster_tool is tools.build_term_cluster_tool
    assert (
        runtime_surface.evaluate_term_retrieval_quality_tool
        is tools.evaluate_term_retrieval_quality_tool
    )
    assert (
        runtime_surface.recommend_narrower_terms_tool
        is tools.recommend_narrower_terms_tool
    )
    assert runtime_surface.rank_candidate_anchors_tool is tools.rank_candidate_anchors_tool
    assert runtime_surface.generate_term_answer_tool is tools.generate_term_answer_tool
    assert runtime_surface.build_chapter_cluster_tool is tools.build_chapter_cluster_tool
    assert runtime_surface.generate_chapter_answer_tool is tools.generate_chapter_answer_tool


def test_runtime_surface_exports_runtime_contracts() -> None:
    assert runtime_surface.RuntimeRequest is runtime_contracts.RuntimeRequest
    assert runtime_surface.RuntimeStepInput is runtime_contracts.RuntimeStepInput
    assert runtime_surface.RuntimeStepResult is runtime_contracts.RuntimeStepResult
    assert runtime_surface.RuntimeResult is runtime_contracts.RuntimeResult
    assert runtime_surface.PlannerDecision is runtime_contracts.PlannerDecision


def test_runtime_surface_exports_runtime_adapter() -> None:
    assert runtime_surface.to_runtime_request is runtime_adapter.to_runtime_request
