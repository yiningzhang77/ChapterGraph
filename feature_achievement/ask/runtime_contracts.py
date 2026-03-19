from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuntimeQueryType = Literal["term", "chapter"]

RuntimeStepStatus = Literal[
    "completed",
    "blocked",
    "needs_more_steps",
    "failed",
]

RuntimeExecutionStatus = Literal[
    "completed",
    "blocked",
    "failed",
]

PlannerActionType = Literal[
    "call_flow",
    "call_tool",
    "finish",
    "block",
]

GraphNodeName = Literal[
    "build_term_cluster",
    "evaluate_term_quality",
    "recommend_narrowing",
    "rank_candidate_anchors",
    "generate_term_answer",
    "build_chapter_cluster",
    "generate_chapter_answer",
]


@dataclass(frozen=True)
class RuntimeRequest:
    query_type: RuntimeQueryType
    run_id: int
    enrichment_version: str
    max_hops: int
    seed_top_k: int
    neighbor_top_k: int
    section_top_k: int
    bullet_top_k: int
    min_edge_score: float
    llm_enabled: bool
    llm_model: str | None
    llm_timeout_ms: int
    term: str | None
    user_query: str | None
    chapter_id: str | None
    query: str | None
    return_cluster: bool
    return_graph_fragment: bool


@dataclass(frozen=True)
class RuntimeStepInput:
    request: RuntimeRequest
    execution_id: str
    step_id: str
    state: dict[str, object]


@dataclass(frozen=True)
class RuntimeStepResult:
    step_id: str
    status: RuntimeStepStatus
    state_patch: dict[str, object]
    emitted_events: list[dict[str, object]]
    blocking_reason: str | None
    error_message: str | None


@dataclass(frozen=True)
class RuntimeResult:
    execution_id: str
    status: RuntimeExecutionStatus
    final_state: dict[str, object]
    answer_markdown: str | None
    runtime_state: str
    events: list[dict[str, object]]
    error_message: str | None


@dataclass(frozen=True)
class PlannerDecision:
    action_type: PlannerActionType
    target_name: str | None
    input_patch: dict[str, object]
    reason: str | None
