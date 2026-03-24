from __future__ import annotations

import re
from typing import Sequence

from feature_achievement.db.models import EnrichedChapter
from feature_achievement.topic_study.membership_contracts import (
    TopicMembershipDecision,
)

__all__ = [
    "build_membership_decisions",
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
