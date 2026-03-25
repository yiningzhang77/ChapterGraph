from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from feature_achievement.topic_study.membership_contracts import RefinedTopicDescriptor

TopicRelationType = Literal[
    "prerequisite",
    "recommended_next",
    "related",
]


@dataclass(frozen=True)
class TopicRelation:
    from_topic_id: str
    to_topic_id: str
    relation_type: TopicRelationType
    reason: str
    score: float | None = None


@dataclass(frozen=True)
class TopicDAG:
    run_id: int
    enrichment_version: str
    topics: list[RefinedTopicDescriptor]
    relations: list[TopicRelation]
    entry_topic_ids: list[str]
