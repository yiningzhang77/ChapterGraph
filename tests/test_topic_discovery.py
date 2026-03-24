from __future__ import annotations

from collections.abc import Iterable

import pytest

from feature_achievement.db.models import Edge, EnrichedChapter, Run
from feature_achievement.topic_study import discovery


def test_group_topic_candidates_creates_components_and_singletons() -> None:
    groups = discovery.group_topic_candidates(
        chapter_ids=[
            "book-a::ch1",
            "book-a::ch2",
            "book-b::ch3",
        ],
        edges=[
            ("book-a::ch1", "book-a::ch2"),
        ],
    )

    assert len(groups) == 2
    assert groups[0].cluster_type == "graph_component"
    assert groups[0].chapter_ids == ["book-a::ch1", "book-a::ch2"]
    assert groups[1].cluster_type == "singleton"
    assert groups[1].chapter_ids == ["book-b::ch3"]


def test_build_topic_id_is_deterministic() -> None:
    first = discovery.build_topic_id(["book-a::ch2", "book-a::ch1"])
    second = discovery.build_topic_id(["book-a::ch1", "book-a::ch2"])

    assert first == second
    assert first.startswith("topic-")


class _FakeResult:
    def __init__(self, values: list[Edge]) -> None:
        self._values = values

    def all(self) -> list[Edge]:
        return self._values


class _FakeSession:
    def __init__(self, edge_rows: list[Edge]) -> None:
        self._edge_rows = edge_rows

    def exec(self, _statement: object) -> _FakeResult:
        return _FakeResult(self._edge_rows)


def test_build_topic_catalog_falls_back_to_chapter_id_for_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run = Run(
        id=5,
        book_ids='["book-a"]',
        enrichment_version="v2_indexed_sections_bullets",
        candidate_generator="embedding",
        similarity="cosine",
        min_score=0.1,
        top_k=40,
    )
    fake_rows = [
        EnrichedChapter(
            id="book-a::ch1",
            book_id="book-a",
            order=1,
            title=None,
            chapter_text="chapter text",
            chapter_index_text="",
            sections=[],
            enrichment_version="v2_indexed_sections_bullets",
        )
    ]

    monkeypatch.setattr(discovery, "get_run", lambda session, run_id: fake_run)
    monkeypatch.setattr(
        discovery,
        "_get_enriched_for_books",
        lambda **kwargs: fake_rows,
    )

    catalog = discovery.build_topic_catalog(
        session=_FakeSession(edge_rows=[]),
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
    )

    assert len(catalog.topics) == 1
    assert catalog.topics[0].label == "book-a::ch1"
    assert catalog.topics[0].description is None


def test_build_topic_catalog_groups_connected_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run = Run(
        id=5,
        book_ids='["book-a","book-b"]',
        enrichment_version="v2_indexed_sections_bullets",
        candidate_generator="embedding",
        similarity="cosine",
        min_score=0.1,
        top_k=40,
    )
    fake_rows = [
        EnrichedChapter(
            id="book-a::ch1",
            book_id="book-a",
            order=1,
            title="Intro A",
            chapter_text="chapter text",
            chapter_index_text="intro a",
            sections=[],
            enrichment_version="v2_indexed_sections_bullets",
        ),
        EnrichedChapter(
            id="book-b::ch2",
            book_id="book-b",
            order=2,
            title="Intro B",
            chapter_text="chapter text",
            chapter_index_text="intro b",
            sections=[],
            enrichment_version="v2_indexed_sections_bullets",
        ),
    ]
    fake_edges = [
        Edge(
            run_id=5,
            from_chapter="book-a::ch1",
            to_chapter="book-b::ch2",
            score=0.2,
            type="embedding",
        )
    ]

    monkeypatch.setattr(discovery, "get_run", lambda session, run_id: fake_run)
    monkeypatch.setattr(
        discovery,
        "_get_enriched_for_books",
        lambda **kwargs: fake_rows,
    )

    catalog = discovery.build_topic_catalog(
        session=_FakeSession(edge_rows=fake_edges),
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
    )

    assert len(catalog.topics) == 1
    assert catalog.topics[0].cluster_type == "graph_component"
    assert catalog.topics[0].chapter_ids == ["book-a::ch1", "book-b::ch2"]
