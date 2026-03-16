from typing import cast

import pytest
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


def test_rank_candidate_anchors_preserves_input_order_before_reranking(
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
        "Spring Data",
        "data persistence",
    ]
