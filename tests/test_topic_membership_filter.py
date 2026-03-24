from __future__ import annotations

from feature_achievement.db.models import EnrichedChapter
from feature_achievement.topic_study.contracts import TopicCatalog, TopicDescriptor, TopicMembership
from feature_achievement.topic_study.membership_filter import (
    build_membership_decisions,
    build_refined_topic_catalog,
    detect_broad_topic,
    select_representative_chapter,
)
from feature_achievement.topic_study.membership_contracts import TopicMembershipDecision


class _FakeResult:
    def __init__(self, values: list[EnrichedChapter]) -> None:
        self._values = values

    def all(self) -> list[EnrichedChapter]:
        return self._values


class _FakeSession:
    def __init__(self, chapter_rows: list[EnrichedChapter]) -> None:
        self._chapter_rows = chapter_rows

    def exec(self, _statement: object) -> _FakeResult:
        return _FakeResult(self._chapter_rows)


def _chapter(
    *,
    chapter_id: str,
    book_id: str,
    order: int,
    title: str,
    chapter_index_text: str,
) -> EnrichedChapter:
    return EnrichedChapter(
        id=chapter_id,
        book_id=book_id,
        order=order,
        title=title,
        chapter_text="",
        chapter_index_text=chapter_index_text,
        sections=[],
        enrichment_version="v2_indexed_sections_bullets",
    )


def test_select_representative_chapter_prefers_textual_center() -> None:
    rows = [
        _chapter(
            chapter_id="book-a::ch1",
            book_id="book-a",
            order=1,
            title="Spring Data Persistence",
            chapter_index_text="spring data persistence jdbc repositories",
        ),
        _chapter(
            chapter_id="book-b::ch2",
            book_id="book-b",
            order=2,
            title="Transactions",
            chapter_index_text="data transactions",
        ),
        _chapter(
            chapter_id="book-c::ch3",
            book_id="book-c",
            order=3,
            title="Actuator and Monitoring",
            chapter_index_text="actuator health metrics monitoring",
        ),
    ]

    representative = select_representative_chapter(rows)

    assert representative.id == "book-a::ch1"


def test_build_membership_decisions_assigns_core_peripheral_and_excluded() -> None:
    rows = [
        _chapter(
            chapter_id="book-a::ch1",
            book_id="book-a",
            order=1,
            title="Working with Data",
            chapter_index_text="spring data persistence jdbc repositories",
        ),
        _chapter(
            chapter_id="book-b::ch2",
            book_id="book-b",
            order=2,
            title="Transactions",
            chapter_index_text="data transactions",
        ),
        _chapter(
            chapter_id="book-c::ch3",
            book_id="book-c",
            order=3,
            title="Actuator and Monitoring",
            chapter_index_text="actuator health metrics monitoring endpoints",
        ),
    ]

    _, decisions = build_membership_decisions(topic_id="topic-x", rows=rows)
    roles = {item.chapter_id: item.member_role for item in decisions}

    assert roles["book-a::ch1"] == "core"
    assert roles["book-b::ch2"] == "peripheral"
    assert roles["book-c::ch3"] == "excluded"


def test_detect_broad_topic_flags_large_topics_with_peripheral_tail() -> None:
    decisions = [
        TopicMembershipDecision("topic-broad", "a", "core", "representative_chapter", 1.0),
        TopicMembershipDecision("topic-broad", "b", "core", "core_similarity", 0.44),
        TopicMembershipDecision("topic-broad", "c", "core", "core_similarity", 0.35),
        TopicMembershipDecision("topic-broad", "d", "core", "core_similarity", 0.29),
        TopicMembershipDecision("topic-broad", "e", "peripheral", "peripheral_similarity", 0.19),
        TopicMembershipDecision("topic-broad", "f", "peripheral", "peripheral_similarity", 0.16),
        TopicMembershipDecision("topic-broad", "g", "excluded", "weak_similarity", 0.02),
    ]

    assert detect_broad_topic(decisions=decisions) is True


def test_build_refined_topic_catalog_preserves_membership_shape() -> None:
    rows = [
        _chapter(
            chapter_id="book-a::ch1",
            book_id="book-a",
            order=1,
            title="Working with Data",
            chapter_index_text="spring data persistence jdbc repositories",
        ),
        _chapter(
            chapter_id="book-b::ch2",
            book_id="book-b",
            order=2,
            title="Transactions",
            chapter_index_text="data transactions",
        ),
        _chapter(
            chapter_id="book-c::ch3",
            book_id="book-c",
            order=3,
            title="Actuator and Monitoring",
            chapter_index_text="actuator health metrics monitoring endpoints",
        ),
    ]
    catalog = TopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            TopicDescriptor(
                topic_id="topic-x",
                label="Working with Data",
                description="raw topic",
                cluster_type="graph_component",
                book_ids=["book-a", "book-b", "book-c"],
                chapter_ids=[row.id for row in rows],
                seed_chapter_id="book-a::ch1",
                memberships=[
                    TopicMembership(
                        topic_id="topic-x",
                        chapter_id=row.id,
                        membership_reason="graph_component",
                        membership_score=None,
                    )
                    for row in rows
                ],
            )
        ],
    )

    refined = build_refined_topic_catalog(
        session=_FakeSession(rows),
        topic_catalog=catalog,
    )

    assert len(refined.topics) == 1
    topic = refined.topics[0]
    assert topic.representative_chapter_id == "book-a::ch1"
    assert topic.core_chapter_ids == ["book-a::ch1"]
    assert topic.peripheral_chapter_ids == ["book-b::ch2"]
    assert topic.excluded_chapter_ids == ["book-c::ch3"]
    assert topic.book_ids == ["book-a", "book-b"]
    assert topic.broad_topic_flag is False
