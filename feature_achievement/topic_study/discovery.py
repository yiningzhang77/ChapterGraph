from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Iterable

from feature_achievement.topic_study.contracts import TopicClusterType, TopicMembership

__all__ = [
    "TopicCandidateGroup",
    "build_topic_id",
    "group_topic_candidates",
]


@dataclass(frozen=True)
class TopicCandidateGroup:
    topic_id: str
    cluster_type: TopicClusterType
    chapter_ids: list[str]
    seed_chapter_id: str
    memberships: list[TopicMembership]


def build_topic_id(chapter_ids: Iterable[str]) -> str:
    ordered_ids = sorted(chapter_ids)
    digest = sha1("|".join(ordered_ids).encode("utf-8")).hexdigest()[:12]
    return f"topic-{digest}"


def group_topic_candidates(
    *,
    chapter_ids: Iterable[str],
    edges: Iterable[tuple[str, str]],
) -> list[TopicCandidateGroup]:
    known_ids = sorted({chapter_id for chapter_id in chapter_ids})
    adjacency: dict[str, set[str]] = {chapter_id: set() for chapter_id in known_ids}

    for source, target in edges:
        if source == target:
            continue
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)

    visited: set[str] = set()
    groups: list[TopicCandidateGroup] = []

    for chapter_id in known_ids:
        if chapter_id in visited:
            continue
        component = _walk_component(seed_id=chapter_id, adjacency=adjacency, visited=visited)
        cluster_type: TopicClusterType = (
            "singleton" if len(component) == 1 else "graph_component"
        )
        topic_id = build_topic_id(component)
        seed_chapter_id = component[0]
        groups.append(
            TopicCandidateGroup(
                topic_id=topic_id,
                cluster_type=cluster_type,
                chapter_ids=component,
                seed_chapter_id=seed_chapter_id,
                memberships=[
                    TopicMembership(
                        topic_id=topic_id,
                        chapter_id=member_id,
                        membership_reason=cluster_type,
                        membership_score=None,
                    )
                    for member_id in component
                ],
            )
        )

    return sorted(groups, key=lambda group: group.seed_chapter_id)


def _walk_component(
    *,
    seed_id: str,
    adjacency: dict[str, set[str]],
    visited: set[str],
) -> list[str]:
    queue = [seed_id]
    component: list[str] = []

    while queue:
        current_id = queue.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        component.append(current_id)
        queue.extend(sorted(adjacency[current_id], reverse=True))

    return sorted(component)
