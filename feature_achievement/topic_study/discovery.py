from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from typing import Iterable

from sqlmodel import Session, select

from feature_achievement.topic_study.contracts import TopicClusterType, TopicMembership
from feature_achievement.topic_study.contracts import TopicCatalog, TopicDescriptor
from feature_achievement.db.ask_queries import get_run
from feature_achievement.db.models import Edge, EnrichedChapter

__all__ = [
    "TopicCandidateGroup",
    "build_topic_catalog",
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


def build_topic_catalog(
    *,
    session: Session,
    run_id: int,
    enrichment_version: str,
) -> TopicCatalog:
    run = get_run(session, run_id)
    if run is None:
        raise ValueError(f"run not found: {run_id}")
    if run.enrichment_version != enrichment_version:
        raise ValueError(
            "run enrichment version mismatch: "
            f"{run.enrichment_version} != {enrichment_version}"
        )

    book_ids = _parse_book_ids(run.book_ids)
    chapter_rows = _get_enriched_for_books(
        session=session,
        book_ids=book_ids,
        enrichment_version=enrichment_version,
    )
    chapter_by_id = {row.id: row for row in chapter_rows}
    chapter_ids = list(chapter_by_id.keys())

    edge_stmt = (
        select(Edge)
        .where(Edge.run_id == run_id)
        .where(Edge.score >= run.min_score)
    )
    edge_rows = session.exec(edge_stmt).all()
    groups = group_topic_candidates(
        chapter_ids=chapter_ids,
        edges=[
            (edge.from_chapter, edge.to_chapter)
            for edge in edge_rows
        ],
    )

    topics: list[TopicDescriptor] = []
    for group in groups:
        member_rows = [
            chapter_by_id[chapter_id]
            for chapter_id in group.chapter_ids
            if chapter_id in chapter_by_id
        ]
        if not member_rows:
            continue

        ordered_rows = sorted(
            member_rows,
            key=lambda row: (
                row.book_id,
                _sort_order(row.order),
                row.id,
            ),
        )
        representative = min(
            member_rows,
            key=lambda row: (
                _sort_order(row.order),
                row.book_id,
                row.id,
            ),
        )
        topics.append(
            TopicDescriptor(
                topic_id=group.topic_id,
                label=_topic_label(representative),
                description=_topic_description(representative),
                cluster_type=group.cluster_type,
                book_ids=_ordered_unique([row.book_id for row in ordered_rows]),
                chapter_ids=[row.id for row in ordered_rows],
                seed_chapter_id=representative.id,
                memberships=group.memberships,
            )
        )

    return TopicCatalog(
        run_id=run_id,
        enrichment_version=enrichment_version,
        topics=topics,
    )


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


def _parse_book_ids(book_ids_json: str) -> list[str]:
    try:
        parsed = json.loads(book_ids_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid run.book_ids payload: {book_ids_json}") from exc
    if not isinstance(parsed, list):
        raise ValueError("run.book_ids must decode to a list")
    return [value for value in parsed if isinstance(value, str)]


def _get_enriched_for_books(
    *,
    session: Session,
    book_ids: list[str],
    enrichment_version: str,
) -> list[EnrichedChapter]:
    if not book_ids:
        return []
    stmt = (
        select(EnrichedChapter)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.book_id.in_(book_ids))
    )
    return session.exec(stmt).all()


def _sort_order(value: int | None) -> int:
    if isinstance(value, int):
        return value
    return 10**9


def _topic_label(row: EnrichedChapter) -> str:
    if isinstance(row.title, str) and row.title.strip():
        return row.title.strip()
    return row.id


def _topic_description(row: EnrichedChapter) -> str | None:
    text = row.chapter_index_text.strip()
    if not text:
        return None
    if len(text) <= 240:
        return text
    return text[:237] + "..."


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
