from __future__ import annotations

import re

from feature_achievement.topic_study.dag_contracts import TopicRelation
from feature_achievement.topic_study.membership_contracts import (
    RefinedTopicCatalog,
    RefinedTopicDescriptor,
)

__all__ = [
    "infer_topic_relations",
]

FOUNDATIONAL_CUES = {
    "bootstarting": 4,
    "getting started": 4,
    "spring in the real world": 4,
    "fundamentals": 4,
    "understanding spring boot": 2,
}

SPECIALIZATION_CUES = {
    "configuration": 1,
    "data": 1,
    "rest": 1,
    "web": 1,
    "security": 2,
    "securing": 2,
    "testing": 2,
    "reactive": 2,
    "monitoring": 2,
    "administering": 2,
    "deploying": 2,
}


def infer_topic_relations(
    *,
    catalog: RefinedTopicCatalog,
) -> list[TopicRelation]:
    topics = sorted(catalog.topics, key=lambda item: item.topic_id)
    relations: list[TopicRelation] = []

    for index, left in enumerate(topics):
        for right in topics[index + 1 :]:
            if left.broad_topic_flag or right.broad_topic_flag:
                continue

            left_to_right = _directional_relation_score(source=left, target=right)
            right_to_left = _directional_relation_score(source=right, target=left)

            relation = _pick_directional_relation(
                left=left,
                right=right,
                left_to_right=left_to_right,
                right_to_left=right_to_left,
            )
            if relation is not None:
                relations.append(relation)

    return sorted(
        relations,
        key=lambda item: (
            item.from_topic_id,
            item.to_topic_id,
            item.relation_type,
        ),
    )


def _pick_directional_relation(
    *,
    left: RefinedTopicDescriptor,
    right: RefinedTopicDescriptor,
    left_to_right: tuple[float, list[str]],
    right_to_left: tuple[float, list[str]],
) -> TopicRelation | None:
    left_score, left_reasons = left_to_right
    right_score, right_reasons = right_to_left

    if left_score < 0.6 and right_score < 0.6:
        return None
    if abs(left_score - right_score) < 0.1:
        return None

    if left_score > right_score:
        return TopicRelation(
            from_topic_id=left.topic_id,
            to_topic_id=right.topic_id,
            relation_type="prerequisite",
            reason="; ".join(left_reasons),
            score=round(left_score, 4),
        )

    return TopicRelation(
        from_topic_id=right.topic_id,
        to_topic_id=left.topic_id,
        relation_type="prerequisite",
        reason="; ".join(right_reasons),
        score=round(right_score, 4),
    )


def _directional_relation_score(
    *,
    source: RefinedTopicDescriptor,
    target: RefinedTopicDescriptor,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    book_order_support = _shared_book_order_support(source=source, target=target)
    if book_order_support > 0:
        score += 0.45
        reasons.append("shared_book_order_support")

    foundation_gap = _foundationality_score(source) - _foundationality_score(target)
    if foundation_gap >= 2:
        score += 0.2
        reasons.append("foundational_before_specialized")

    label_score = _label_transition_support(source=source, target=target)
    if label_score > 0:
        score += label_score
        reasons.append("topic_label_cue")

    if _is_cross_book_topic(source) and book_order_support > 0 and foundation_gap >= 1:
        score += 0.15
        reasons.append("cross_book_anchor_support")

    return score, reasons


def _shared_book_order_support(
    *,
    source: RefinedTopicDescriptor,
    target: RefinedTopicDescriptor,
) -> float:
    shared_books = sorted(set(source.book_ids).intersection(target.book_ids))
    if not shared_books:
        return 0.0

    supporting_books = 0
    for book_id in shared_books:
        source_orders = _orders_for_book(topic=source, book_id=book_id)
        target_orders = _orders_for_book(topic=target, book_id=book_id)
        if not source_orders or not target_orders:
            continue
        if max(source_orders) < min(target_orders):
            gap = min(target_orders) - max(source_orders)
            if gap <= 4:
                supporting_books += 1
        elif max(target_orders) < min(source_orders):
            return 0.0

    if supporting_books == 0:
        return 0.0
    return float(supporting_books)


def _label_transition_support(
    *,
    source: RefinedTopicDescriptor,
    target: RefinedTopicDescriptor,
) -> float:
    source_label = source.label.lower()
    target_label = target.label.lower()

    if any(token in source_label for token in ("bootstarting", "getting started", "spring in the real world")):
        if any(token in target_label for token in ("configuration", "rest", "security", "testing", "deploying", "data", "web")):
            return 0.15

    if any(token in source_label for token in ("rest", "web")) and "secur" in target_label:
        return 0.25

    if "configuration" in source_label and any(token in target_label for token in ("data", "rest", "security")):
        return 0.2

    return 0.0


def _foundationality_score(topic: RefinedTopicDescriptor) -> int:
    label = topic.label.lower()
    score = 0
    for phrase, value in FOUNDATIONAL_CUES.items():
        if phrase in label:
            score += value
    for phrase, value in SPECIALIZATION_CUES.items():
        if phrase in label:
            score -= value
    return score


def _orders_for_book(
    *,
    topic: RefinedTopicDescriptor,
    book_id: str,
) -> list[int]:
    orders: list[int] = []
    for chapter_id in topic.core_chapter_ids + topic.peripheral_chapter_ids:
        if not chapter_id.startswith(f"{book_id}::"):
            continue
        order = _chapter_order(chapter_id)
        if order is not None:
            orders.append(order)
    return sorted(orders)


def _chapter_order(chapter_id: str) -> int | None:
    match = re.search(r"::ch(\d+)$", chapter_id)
    if match is None:
        return None
    return int(match.group(1))


def _is_cross_book_topic(topic: RefinedTopicDescriptor) -> bool:
    return len(topic.book_ids) >= 2
