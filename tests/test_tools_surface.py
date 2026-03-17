from feature_achievement.ask import chapter_flow, term_flow, tools


def test_unified_tool_surface_exports_expected_names() -> None:
    assert tools.build_term_cluster_tool is not None
    assert tools.evaluate_term_retrieval_quality_tool is not None
    assert tools.recommend_narrower_terms_tool is not None
    assert tools.rank_candidate_anchors_tool is not None
    assert tools.generate_term_answer_tool is not None
    assert tools.build_chapter_cluster_tool is not None
    assert tools.generate_chapter_answer_tool is not None


def test_term_flow_imports_tools_from_unified_surface() -> None:
    assert term_flow.build_term_cluster_tool is tools.build_term_cluster_tool
    assert (
        term_flow.evaluate_term_retrieval_quality_tool
        is tools.evaluate_term_retrieval_quality_tool
    )
    assert term_flow.recommend_narrower_terms_tool is tools.recommend_narrower_terms_tool
    assert term_flow.rank_candidate_anchors_tool is tools.rank_candidate_anchors_tool
    assert term_flow.generate_term_answer_tool is tools.generate_term_answer_tool


def test_chapter_flow_imports_tools_from_unified_surface() -> None:
    assert chapter_flow.build_chapter_cluster_tool is tools.build_chapter_cluster_tool
    assert chapter_flow.generate_chapter_answer_tool is tools.generate_chapter_answer_tool
