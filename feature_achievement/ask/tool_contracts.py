from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClusterToolResult:
    term: str
    run_id: int
    enrichment_version: str
    cluster: dict[str, object]
    evidence: dict[str, object] | None
    seed_ids: list[str]


@dataclass(frozen=True)
class RetrievalQualityToolResult:
    state: str | None
    retrieval_warnings: dict[str, object] | None
    response_guidance: str | None


@dataclass(frozen=True)
class NarrowingRecommendationToolResult:
    suggested_terms: list[str]
    recommendation_reason: str | None
    recommendation_source: str | None
    recommendation_confidence: str | None


@dataclass(frozen=True)
class CandidateAnchorDiagnostic:
    term: str
    focus_state: str
    expected_response_state: str
    seed_count: int
    evidence_chapter_count: int
    evidence_book_count: int
    source: str


@dataclass(frozen=True)
class CandidateAnchorRankingToolResult:
    suggested_terms: list[str]
    diagnostics: list[CandidateAnchorDiagnostic]


@dataclass(frozen=True)
class TermAnswerToolResult:
    answer_markdown: str | None
    llm_error: str | None
