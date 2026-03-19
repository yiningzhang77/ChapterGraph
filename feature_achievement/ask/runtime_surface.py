from __future__ import annotations

"""Thin runtime-facing surface for future agent/runtime callers."""

from feature_achievement.ask.chapter_flow import run_chapter_flow
from feature_achievement.ask.term_flow import run_term_flow
from feature_achievement.ask.tools import (
    build_chapter_cluster_tool,
    build_term_cluster_tool,
    evaluate_term_retrieval_quality_tool,
    generate_chapter_answer_tool,
    generate_term_answer_tool,
    rank_candidate_anchors_tool,
    recommend_narrower_terms_tool,
)

__all__ = [
    "run_term_flow",
    "run_chapter_flow",
    "build_term_cluster_tool",
    "evaluate_term_retrieval_quality_tool",
    "recommend_narrower_terms_tool",
    "rank_candidate_anchors_tool",
    "generate_term_answer_tool",
    "build_chapter_cluster_tool",
    "generate_chapter_answer_tool",
]
