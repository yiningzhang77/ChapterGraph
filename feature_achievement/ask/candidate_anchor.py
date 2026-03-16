from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    EVIDENCE_SCATTER_BOOK_THRESHOLD,
    EVIDENCE_SCATTER_CHAPTER_THRESHOLD,
    TERM_TOO_BROAD_SEED_THRESHOLD,
    default_term_user_query,
    evaluate_term_retrieval_quality,
)


def evaluate_candidate_anchor(
    *,
    term: str,
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> dict[str, object]:
    probe = _probe_candidate_cluster(
        session=session,
        term=term,
        user_query=user_query,
        run_id=run_id,
        enrichment_version=enrichment_version,
    )
    seed_count = _int_value(probe.get("seed_count"))
    evidence_chapter_count = _int_value(probe.get("evidence_chapter_count"))
    evidence_book_count = _int_value(probe.get("evidence_book_count"))

    if probe.get("status") == "no_seed":
        return {
            "term": term,
            "focus_state": "no_seed",
            "expected_response_state": "no_seed",
            "seed_count": 0,
            "evidence_chapter_count": 0,
            "evidence_book_count": 0,
            "source": "retrieval_probe",
        }

    retrieval_state = probe.get("retrieval_state")
    if retrieval_state == "broad_allowed":
        expected_response_state = "broad_overview"
        focus_state = "acceptable"
    elif retrieval_state == "broad_blocked":
        expected_response_state = "needs_narrower_term"
        focus_state = "broad"
    else:
        is_broad = (
            seed_count >= TERM_TOO_BROAD_SEED_THRESHOLD
            or evidence_chapter_count >= EVIDENCE_SCATTER_CHAPTER_THRESHOLD
            or evidence_book_count >= EVIDENCE_SCATTER_BOOK_THRESHOLD
        )
        expected_response_state = "needs_narrower_term" if is_broad else "normal"
        focus_state = "broad" if is_broad else "focused"

    return {
        "term": term,
        "focus_state": focus_state,
        "expected_response_state": expected_response_state,
        "seed_count": seed_count,
        "evidence_chapter_count": evidence_chapter_count,
        "evidence_book_count": evidence_book_count,
        "source": "retrieval_probe",
    }


def rank_candidate_anchors(
    *,
    terms: list[str],
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> list[dict[str, object]]:
    return [
        evaluate_candidate_anchor(
            term=term,
            user_query=user_query,
            run_id=run_id,
            enrichment_version=enrichment_version,
            session=session,
        )
        for term in terms
    ]


def _probe_candidate_cluster(
    *,
    session: Session,
    term: str,
    user_query: str,
    run_id: int,
    enrichment_version: str,
) -> dict[str, object]:
    req = AskRequest(
        query_type="term",
        term=term,
        user_query=user_query,
        run_id=run_id,
        enrichment_version=enrichment_version,
        llm_enabled=False,
        return_cluster=False,
        return_graph_fragment=False,
    )
    try:
        cluster = build_cluster(session=session, req=req)
    except HTTPException as exc:
        if exc.status_code == 422:
            return {"status": "no_seed"}
        raise

    evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
    cluster_payload = dict(cluster)
    cluster_payload.pop("evidence", None)
    quality = evaluate_term_retrieval_quality(
        term=term,
        user_query=req.user_query or default_term_user_query(term),
        user_query_was_default=req.user_query == default_term_user_query(term),
        cluster=cluster_payload,
        evidence=evidence,
    )
    return {
        "status": "ok",
        "seed_count": _seed_count(cluster_payload),
        "evidence_chapter_count": _evidence_chapter_count(evidence),
        "evidence_book_count": _evidence_book_count(cluster_payload, evidence),
        "retrieval_state": quality.get("state") if isinstance(quality, dict) else "normal",
    }


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0


def _seed_count(cluster: dict[str, object]) -> int:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return 0
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return 0
    return sum(1 for seed_id in seed_ids if isinstance(seed_id, str))


def _evidence_chapter_count(evidence: dict[str, object] | None) -> int:
    bullets = evidence.get("bullets") if isinstance(evidence, dict) else None
    if not isinstance(bullets, list):
        return 0
    chapter_ids = {
        chapter_id
        for bullet in bullets
        if isinstance(bullet, dict)
        for chapter_id in [bullet.get("chapter_id")]
        if isinstance(chapter_id, str)
    }
    return len(chapter_ids)


def _evidence_book_count(
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
) -> int:
    chapters = cluster.get("chapters")
    if not isinstance(chapters, list):
        return 0
    chapter_to_book = {
        chapter_id: book_id
        for chapter in chapters
        if isinstance(chapter, dict)
        for chapter_id in [chapter.get("chapter_id")]
        for book_id in [chapter.get("book_id")]
        if isinstance(chapter_id, str) and isinstance(book_id, str)
    }
    bullets = evidence.get("bullets") if isinstance(evidence, dict) else None
    if not isinstance(bullets, list):
        return 0
    book_ids = {
        chapter_to_book[chapter_id]
        for bullet in bullets
        if isinstance(bullet, dict)
        for chapter_id in [bullet.get("chapter_id")]
        if isinstance(chapter_id, str) and chapter_id in chapter_to_book
    }
    return len(book_ids)
