from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import cluster_builder


@dataclass
class RunStub:
    enrichment_version: str


@dataclass
class EdgeStub:
    from_chapter: str
    to_chapter: str
    score: float
    type: str


@dataclass
class EnrichedStub:
    id: str
    book_id: str
    title: str
    chapter_text: str
    sections: list[str]
    signals: dict[str, object]


def _req(**overrides: object) -> AskRequest:
    payload: dict[str, object] = {
        "query": "Actuator",
        "query_type": "term",
        "run_id": 1,
        "enrichment_version": "v1_bullets+sections",
        "max_hops": 2,
        "seed_top_k": 5,
        "neighbor_top_k": 40,
        "min_edge_score": 0.2,
    }
    payload.update(overrides)
    return AskRequest.model_validate(payload)


def test_missing_run_raises_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cluster_builder, "get_run", lambda session, run_id: None)
    req = _req()
    with pytest.raises(HTTPException) as exc:
        cluster_builder.build_cluster(Session(), req)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Run not found"


def test_version_mismatch_raises_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cluster_builder,
        "get_run",
        lambda session, run_id: RunStub(enrichment_version="v0"),
    )
    req = _req()
    with pytest.raises(HTTPException) as exc:
        cluster_builder.build_cluster(Session(), req)
    assert exc.value.status_code == 409
    assert "does not match" in str(exc.value.detail)


def test_no_seed_found_raises_422(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cluster_builder,
        "get_run",
        lambda session, run_id: RunStub(enrichment_version="v1_bullets+sections"),
    )
    monkeypatch.setattr(
        cluster_builder,
        "_pick_seed_ids",
        lambda session, req: ([], "term_ilike"),
    )
    req = _req()
    with pytest.raises(HTTPException) as exc:
        cluster_builder.build_cluster(Session(), req)
    assert exc.value.status_code == 422
    assert exc.value.detail == "No seed chapters found"


def test_successful_cluster_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cluster_builder,
        "get_run",
        lambda session, run_id: RunStub(enrichment_version="v1_bullets+sections"),
    )
    monkeypatch.setattr(
        cluster_builder,
        "_pick_seed_ids",
        lambda session, req: (["book::ch1"], "term_ilike"),
    )
    monkeypatch.setattr(
        cluster_builder,
        "get_edges_from_sources",
        lambda session, run_id, source_ids, min_edge_score, limit: [
            EdgeStub(
                from_chapter="book::ch1",
                to_chapter="book::ch2",
                score=0.7,
                type="tfidf",
            )
        ],
    )
    monkeypatch.setattr(
        cluster_builder,
        "get_enriched_by_ids",
        lambda session, chapter_ids, enrichment_version: [
            EnrichedStub(
                id="book::ch1",
                book_id="book",
                title="T1",
                chapter_text="a",
                sections=["s1"],
                signals={"bullets": ["b1"]},
            ),
            EnrichedStub(
                id="book::ch2",
                book_id="book",
                title="T2",
                chapter_text="b",
                sections=["s2"],
                signals={"bullets": ["b2"]},
            ),
        ],
    )

    req = _req()
    cluster = cluster_builder.build_cluster(Session(), req)

    assert cluster["schema_version"] == "cluster.v1"
    assert cluster["query_type"] == "term"

    seed = cluster["seed"]
    assert isinstance(seed, dict)
    assert seed["seed_reason"] == "term_ilike"
    assert seed["seed_chapter_ids"] == ["book::ch1"]

    chapters = cluster["chapters"]
    edges = cluster["edges"]
    assert isinstance(chapters, list)
    assert isinstance(edges, list)
    assert len(chapters) == 2
    assert len(edges) == 1

