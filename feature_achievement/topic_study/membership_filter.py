from __future__ import annotations

import re
from typing import Sequence

from sqlmodel import Session, select

from feature_achievement.db.models import EnrichedChapter
from feature_achievement.topic_study.contracts import TopicCatalog
from feature_achievement.topic_study.membership_contracts import (
    RefinedTopicCatalog,
    RefinedTopicDescriptor,
    TopicMembershipDecision,
)

__all__ = [
    "build_refined_topic_catalog",
    "build_membership_decisions",
    "detect_broad_topic",
    "score_membership_against_representative",
    "select_representative_chapter",
]

CORE_SCORE_THRESHOLD = 0.22
PERIPHERAL_SCORE_THRESHOLD = 0.08


def select_representative_chapter(rows: Sequence[EnrichedChapter]) -> EnrichedChapter:
    if not rows:
        raise ValueError("cannot select representative chapter from empty rows")

    return min(
        rows,
        key=lambda row: (
            -_representative_centrality(row=row, rows=rows),
            _sort_order(row.order),
            row.book_id,
            row.id,
        ),
    )


def score_membership_against_representative(
    *,
    representative: EnrichedChapter,
    candidate: EnrichedChapter,
) -> float:
    if representative.id == candidate.id:
        return 1.0
    return _jaccard_similarity(_chapter_text_basis(representative), _chapter_text_basis(candidate))


def build_membership_decisions(
    *,
    topic_id: str,
    rows: Sequence[EnrichedChapter],
) -> tuple[EnrichedChapter, list[TopicMembershipDecision]]:
    representative = select_representative_chapter(rows)
    decisions: list[TopicMembershipDecision] = []

    for row in sorted(rows, key=lambda item: (_sort_order(item.order), item.book_id, item.id)):
        score = score_membership_against_representative(
            representative=representative,
            candidate=row,
        )
        if row.id == representative.id:
            role = "core"
            reason = "representative_chapter"
        elif score >= CORE_SCORE_THRESHOLD:
            role = "core"
            reason = "core_similarity"
        elif score >= PERIPHERAL_SCORE_THRESHOLD:
            role = "peripheral"
            reason = "peripheral_similarity"
        else:
            role = "excluded"
            reason = "weak_similarity"

        decisions.append(
            TopicMembershipDecision(
                topic_id=topic_id,
                chapter_id=row.id,
                member_role=role,
                reason=reason,
                score=round(score, 4),
            )
        )

    return representative, decisions


def detect_broad_topic(
    *,
    decisions: Sequence[TopicMembershipDecision],
) -> bool:
    core_count = sum(1 for item in decisions if item.member_role == "core")
    peripheral_count = sum(1 for item in decisions if item.member_role == "peripheral")
    excluded_count = sum(1 for item in decisions if item.member_role == "excluded")
    total = len(decisions)

    if total >= 6 and peripheral_count >= 2:
        return True
    if total >= 6 and excluded_count >= 2:
        return True
    if total >= 5 and peripheral_count >= 2 and excluded_count >= 1:
        return True
    if total >= 6 and core_count <= max(2, total // 3):
        return True
    return False


def build_refined_topic_catalog(
    *,
    session: Session,
    topic_catalog: TopicCatalog,
) -> RefinedTopicCatalog:
    chapter_ids = sorted(
        {
            chapter_id
            for topic in topic_catalog.topics
            for chapter_id in topic.chapter_ids
        }
    )
    chapter_by_id = _get_enriched_by_ids(
        session=session,
        chapter_ids=chapter_ids,
        enrichment_version=topic_catalog.enrichment_version,
    )

    topics: list[RefinedTopicDescriptor] = []
    for topic in topic_catalog.topics:
        member_rows = [
            chapter_by_id[chapter_id]
            for chapter_id in topic.chapter_ids
            if chapter_id in chapter_by_id
        ]
        if not member_rows:
            continue

        representative, decisions = build_membership_decisions(
            topic_id=topic.topic_id,
            rows=member_rows,
        )
        core_chapter_ids = [
            item.chapter_id
            for item in decisions
            if item.member_role == "core"
        ]
        peripheral_chapter_ids = [
            item.chapter_id
            for item in decisions
            if item.member_role == "peripheral"
        ]
        excluded_chapter_ids = [
            item.chapter_id
            for item in decisions
            if item.member_role == "excluded"
        ]
        included_rows = [
            chapter_by_id[chapter_id]
            for chapter_id in core_chapter_ids + peripheral_chapter_ids
            if chapter_id in chapter_by_id
        ]
        topics.append(
            RefinedTopicDescriptor(
                topic_id=topic.topic_id,
                label=_topic_label(representative),
                description=_topic_description(representative),
                representative_chapter_id=representative.id,
                core_chapter_ids=core_chapter_ids,
                peripheral_chapter_ids=peripheral_chapter_ids,
                excluded_chapter_ids=excluded_chapter_ids,
                book_ids=_ordered_unique([row.book_id for row in included_rows]),
                broad_topic_flag=detect_broad_topic(decisions=decisions),
                membership_decisions=decisions,
            )
        )

    return RefinedTopicCatalog(
        run_id=topic_catalog.run_id,
        enrichment_version=topic_catalog.enrichment_version,
        topics=topics,
    )


def _representative_centrality(
    *,
    row: EnrichedChapter,
    rows: Sequence[EnrichedChapter],
) -> float:
    if len(rows) == 1:
        return 1.0

    total = 0.0
    count = 0
    for other in rows:
        if other.id == row.id:
            continue
        total += _jaccard_similarity(_chapter_text_basis(row), _chapter_text_basis(other))
        count += 1
    if count == 0:
        return 0.0
    return total / count


def _chapter_text_basis(row: EnrichedChapter) -> str:
    title = row.title or ""
    index_text = row.chapter_index_text or ""
    return f"{title} {index_text}".strip()


def _normalize_text(value: str) -> list[str]:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    if not text:
        return []
    return text.split()


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(_normalize_text(left))
    right_tokens = set(_normalize_text(right))
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens.intersection(right_tokens)
    union = left_tokens.union(right_tokens)
    return len(intersection) / len(union)


def _sort_order(value: int | None) -> int:
    if isinstance(value, int):
        return value
    return 10**9


def _get_enriched_by_ids(
    *,
    session: Session,
    chapter_ids: list[str],
    enrichment_version: str,
) -> dict[str, EnrichedChapter]:
    if not chapter_ids:
        return {}
    stmt = (
        select(EnrichedChapter)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.id.in_(chapter_ids))
    )
    rows = session.exec(stmt).all()
    return {row.id: row for row in rows}


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
