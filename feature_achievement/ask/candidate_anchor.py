from __future__ import annotations

from sqlmodel import Session

from feature_achievement.ask.retrieval_quality import (
    EVIDENCE_SCATTER_BOOK_THRESHOLD,
    EVIDENCE_SCATTER_CHAPTER_THRESHOLD,
    TERM_TOO_BROAD_SEED_THRESHOLD,
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

    is_broad = (
        seed_count >= TERM_TOO_BROAD_SEED_THRESHOLD
        or evidence_chapter_count >= EVIDENCE_SCATTER_CHAPTER_THRESHOLD
        or evidence_book_count >= EVIDENCE_SCATTER_BOOK_THRESHOLD
    )
    return {
        "term": term,
        "focus_state": "broad" if is_broad else "focused",
        "expected_response_state": "needs_narrower_term" if is_broad else "normal",
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
    _ = (session, term, user_query, run_id, enrichment_version)
    raise NotImplementedError("Candidate anchor probing is not wired yet.")


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0
