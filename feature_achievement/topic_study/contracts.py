from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TopicClusterType = Literal[
    "singleton",
    "graph_component",
]


@dataclass(frozen=True)
class TopicMembership:
    topic_id: str
    chapter_id: str
    membership_reason: str
    membership_score: float | None = None


@dataclass(frozen=True)
class TopicDescriptor:
    topic_id: str
    label: str
    description: str | None
    cluster_type: TopicClusterType
    book_ids: list[str]
    chapter_ids: list[str]
    seed_chapter_id: str
    memberships: list[TopicMembership]


@dataclass(frozen=True)
class TopicCatalog:
    run_id: int
    enrichment_version: str
    topics: list[TopicDescriptor]
