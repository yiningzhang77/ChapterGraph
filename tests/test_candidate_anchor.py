from typing import cast

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from feature_achievement.ask import candidate_anchor


def test_evaluate_candidate_anchor_returns_normal_for_focused_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "seed_count": 2,
            "evidence_chapter_count": 2,
            "evidence_book_count": 1,
        }

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    result = candidate_anchor.evaluate_candidate_anchor(
        term="data persistence",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result["focus_state"] == "focused"
    assert result["expected_response_state"] == "normal"
    assert result["source"] == "retrieval_probe"


def test_evaluate_candidate_anchor_returns_blocked_for_broad_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {
            "seed_count": 5,
            "evidence_chapter_count": 5,
            "evidence_book_count": 2,
        }

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    result = candidate_anchor.evaluate_candidate_anchor(
        term="Spring Data",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result["focus_state"] == "broad"
    assert result["expected_response_state"] == "needs_narrower_term"


def test_evaluate_candidate_anchor_returns_no_seed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {"status": "no_seed"}

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    result = candidate_anchor.evaluate_candidate_anchor(
        term="Actuatro",
        user_query="Tell me about Actuatro",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result["focus_state"] == "no_seed"
    assert result["expected_response_state"] == "no_seed"
    assert result["seed_count"] == 0


def test_rank_candidate_anchors_places_focused_candidate_before_broad_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        term = kwargs["term"]
        if term == "Spring Data":
            return {"seed_count": 5, "evidence_chapter_count": 5, "evidence_book_count": 2}
        return {"seed_count": 2, "evidence_chapter_count": 2, "evidence_book_count": 1}

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    results = candidate_anchor.rank_candidate_anchors(
        terms=["Spring Data", "data persistence"],
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert [result["term"] for result in results] == [
        "data persistence",
        "Spring Data",
    ]


def test_evaluate_candidate_anchor_reuses_build_cluster_and_retrieval_quality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_cluster(*, session: Session, req: object) -> dict[str, object]:
        captured["session"] = session
        captured["req"] = req
        return {
            "seed": {
                "seed_chapter_ids": ["book0::ch1", "book0::ch2"],
                "seed_reason": "term_ilike",
            },
            "chapters": [
                {"chapter_id": "book0::ch1", "book_id": "book0"},
                {"chapter_id": "book0::ch2", "book_id": "book0"},
            ],
            "edges": [],
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book0::ch1"},
                    {"chapter_id": "book0::ch2"},
                ],
            },
        }

    def fake_quality(**kwargs: object) -> dict[str, object] | None:
        captured["quality_kwargs"] = kwargs
        return None

    monkeypatch.setattr(candidate_anchor, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(
        candidate_anchor,
        "evaluate_term_retrieval_quality",
        fake_quality,
    )

    result = candidate_anchor.evaluate_candidate_anchor(
        term="data persistence",
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    req = captured["req"]
    assert getattr(req, "term") == "data persistence"
    assert getattr(req, "user_query") == "How does Spring implement data persistence?"
    assert result["expected_response_state"] == "normal"
    quality_kwargs = captured["quality_kwargs"]
    assert quality_kwargs["term"] == "data persistence"
    assert quality_kwargs["user_query_was_default"] is False


def test_evaluate_candidate_anchor_maps_broad_allowed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*, session: Session, req: object) -> dict[str, object]:
        _ = (session, req)
        return {
            "seed": {
                "seed_chapter_ids": ["book0::ch1", "book0::ch2"],
                "seed_reason": "term_ilike",
            },
            "chapters": [
                {"chapter_id": "book0::ch1", "book_id": "book0"},
                {"chapter_id": "book0::ch2", "book_id": "book0"},
            ],
            "edges": [],
            "evidence": {
                "sections": [],
                "bullets": [
                    {"chapter_id": "book0::ch1"},
                    {"chapter_id": "book0::ch2"},
                ],
            },
        }

    def fake_quality(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {"state": "broad_allowed"}

    monkeypatch.setattr(candidate_anchor, "build_cluster", fake_build_cluster)
    monkeypatch.setattr(
        candidate_anchor,
        "evaluate_term_retrieval_quality",
        fake_quality,
    )

    result = candidate_anchor.evaluate_candidate_anchor(
        term="Spring",
        user_query="What is Spring?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result["focus_state"] == "acceptable"
    assert result["expected_response_state"] == "broad_overview"


def test_evaluate_candidate_anchor_returns_no_seed_when_cluster_builder_raises_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_cluster(*, session: Session, req: object) -> dict[str, object]:
        _ = (session, req)
        raise HTTPException(status_code=422, detail="No seed chapters found")

    monkeypatch.setattr(candidate_anchor, "build_cluster", fake_build_cluster)

    result = candidate_anchor.evaluate_candidate_anchor(
        term="Actuatro",
        user_query="Tell me about Actuatro",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert result["expected_response_state"] == "no_seed"


def test_rank_candidate_anchors_places_no_seed_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        term = kwargs["term"]
        if term == "Actuatro":
            return {"status": "no_seed"}
        if term == "Spring Data":
            return {"seed_count": 5, "evidence_chapter_count": 5, "evidence_book_count": 2}
        return {"seed_count": 2, "evidence_chapter_count": 2, "evidence_book_count": 1}

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    results = candidate_anchor.rank_candidate_anchors(
        terms=["Actuatro", "Spring Data", "JdbcTemplate"],
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert [result["term"] for result in results] == [
        "JdbcTemplate",
        "Spring Data",
        "Actuatro",
    ]


def test_rank_candidate_anchors_is_deterministic_for_equal_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_probe(**kwargs: object) -> dict[str, object]:
        _ = kwargs
        return {"seed_count": 2, "evidence_chapter_count": 2, "evidence_book_count": 1}

    monkeypatch.setattr(candidate_anchor, "_probe_candidate_cluster", fake_probe)

    results = candidate_anchor.rank_candidate_anchors(
        terms=["JdbcTemplate", "data persistence"],
        user_query="How does Spring implement data persistence?",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        session=cast(Session, object()),
    )

    assert [result["term"] for result in results] == [
        "JdbcTemplate",
        "data persistence",
    ]
