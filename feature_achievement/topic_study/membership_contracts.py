from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TopicMemberRole = Literal[
    "core",
    "peripheral",
    "excluded",
]


@dataclass(frozen=True)
class TopicMembershipDecision:
    topic_id: str
    chapter_id: str
    member_role: TopicMemberRole
    reason: str
    score: float | None = None


@dataclass(frozen=True)
class RefinedTopicDescriptor:
    topic_id: str
    label: str
    description: str | None
    representative_chapter_id: str
    core_chapter_ids: list[str]
    peripheral_chapter_ids: list[str]
    excluded_chapter_ids: list[str]
    book_ids: list[str]
    broad_topic_flag: bool
    membership_decisions: list[TopicMembershipDecision]


@dataclass(frozen=True)
class RefinedTopicCatalog:
    run_id: int
    enrichment_version: str
    topics: list[RefinedTopicDescriptor]
