from __future__ import annotations

from dataclasses import asdict

import pytest

from feature_achievement.topic_study.dag_builder import (
    build_topic_dag,
    infer_topic_relations,
)
from feature_achievement.topic_study.dag_contracts import TopicRelation
from feature_achievement.topic_study.membership_contracts import (
    RefinedTopicCatalog,
    RefinedTopicDescriptor,
)


def _topic(
    *,
    topic_id: str,
    label: str,
    representative_chapter_id: str,
    core_chapter_ids: list[str],
    book_ids: list[str],
    broad_topic_flag: bool = False,
) -> RefinedTopicDescriptor:
    return RefinedTopicDescriptor(
        topic_id=topic_id,
        label=label,
        description=label,
        representative_chapter_id=representative_chapter_id,
        core_chapter_ids=core_chapter_ids,
        peripheral_chapter_ids=[],
        excluded_chapter_ids=[],
        book_ids=book_ids,
        broad_topic_flag=broad_topic_flag,
        membership_decisions=[],
    )


def test_infer_topic_relations_prefers_foundational_topic_before_specialized() -> None:
    catalog = RefinedTopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            _topic(
                topic_id="topic-boot",
                label="1 Bootstarting Spring",
                representative_chapter_id="springboot-in-action::ch1",
                core_chapter_ids=["springboot-in-action::ch1", "springboot-in-action::ch2"],
                book_ids=["springboot-in-action"],
            ),
            _topic(
                topic_id="topic-config",
                label="6 Working with configuration properties",
                representative_chapter_id="springboot-in-action::ch3",
                core_chapter_ids=["springboot-in-action::ch3"],
                book_ids=["springboot-in-action"],
            ),
        ],
    )

    relations = infer_topic_relations(catalog=catalog)

    assert len(relations) == 1
    assert relations[0].from_topic_id == "topic-boot"
    assert relations[0].to_topic_id == "topic-config"
    assert relations[0].relation_type == "prerequisite"


def test_infer_topic_relations_skips_broad_topics() -> None:
    catalog = RefinedTopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            _topic(
                topic_id="topic-boot",
                label="1 Bootstarting Spring",
                representative_chapter_id="springboot-in-action::ch1",
                core_chapter_ids=["springboot-in-action::ch1"],
                book_ids=["springboot-in-action"],
            ),
            _topic(
                topic_id="topic-data-broad",
                label="3 Working with data",
                representative_chapter_id="spring-in-action::ch3",
                core_chapter_ids=["spring-in-action::ch3"],
                book_ids=["spring-in-action", "spring-start-here", "springboot-in-action"],
                broad_topic_flag=True,
            ),
        ],
    )

    relations = infer_topic_relations(catalog=catalog)

    assert relations == []


def test_build_topic_dag_selects_root_entry_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = RefinedTopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            _topic(
                topic_id="topic-boot",
                label="1 Bootstarting Spring",
                representative_chapter_id="springboot-in-action::ch1",
                core_chapter_ids=["springboot-in-action::ch1"],
                book_ids=["springboot-in-action"],
            ),
            _topic(
                topic_id="topic-config",
                label="6 Working with configuration properties",
                representative_chapter_id="springboot-in-action::ch3",
                core_chapter_ids=["springboot-in-action::ch3"],
                book_ids=["springboot-in-action"],
            ),
            _topic(
                topic_id="topic-security",
                label="8 Securing REST",
                representative_chapter_id="spring-in-action::ch8",
                core_chapter_ids=["spring-in-action::ch8"],
                book_ids=["spring-in-action"],
            ),
        ],
    )
    monkeypatch.setattr(
        "feature_achievement.topic_study.dag_builder.infer_topic_relations",
        lambda **kwargs: [
            TopicRelation("topic-boot", "topic-config", "prerequisite", "test", 0.9),
            TopicRelation("topic-config", "topic-security", "prerequisite", "test", 0.9),
        ],
    )

    dag = build_topic_dag(catalog=catalog)

    assert dag.entry_topic_ids == ["topic-boot"]


def test_build_topic_dag_prunes_cycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = RefinedTopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            _topic(
                topic_id="topic-a",
                label="1 Bootstarting Spring",
                representative_chapter_id="book::ch1",
                core_chapter_ids=["book::ch1"],
                book_ids=["book"],
            ),
            _topic(
                topic_id="topic-b",
                label="6 Working with configuration properties",
                representative_chapter_id="book::ch3",
                core_chapter_ids=["book::ch3"],
                book_ids=["book"],
            ),
            _topic(
                topic_id="topic-c",
                label="8 Securing REST",
                representative_chapter_id="book::ch8",
                core_chapter_ids=["book::ch8"],
                book_ids=["book"],
            ),
        ],
    )
    monkeypatch.setattr(
        "feature_achievement.topic_study.dag_builder.infer_topic_relations",
        lambda **kwargs: [
            TopicRelation("topic-a", "topic-b", "prerequisite", "test", 0.9),
            TopicRelation("topic-b", "topic-c", "prerequisite", "test", 0.8),
            TopicRelation("topic-c", "topic-a", "prerequisite", "test", 0.7),
        ],
    )

    dag = build_topic_dag(catalog=catalog)

    assert len(dag.relations) == 2
    assert ("topic-c", "topic-a") not in {
        (item.from_topic_id, item.to_topic_id) for item in dag.relations
    }


def test_build_topic_dag_is_deterministic() -> None:
    catalog = RefinedTopicCatalog(
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        topics=[
            _topic(
                topic_id="topic-boot",
                label="1 Bootstarting Spring",
                representative_chapter_id="springboot-in-action::ch1",
                core_chapter_ids=["springboot-in-action::ch1", "springboot-in-action::ch2"],
                book_ids=["springboot-in-action"],
            ),
            _topic(
                topic_id="topic-config",
                label="6 Working with configuration properties",
                representative_chapter_id="springboot-in-action::ch3",
                core_chapter_ids=["springboot-in-action::ch3"],
                book_ids=["springboot-in-action"],
            ),
        ],
    )

    first = build_topic_dag(catalog=catalog)
    second = build_topic_dag(catalog=catalog)

    assert asdict(first) == asdict(second)
