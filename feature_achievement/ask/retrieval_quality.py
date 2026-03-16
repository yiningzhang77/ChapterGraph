from __future__ import annotations

from collections.abc import Iterable


TERM_TOO_BROAD_SEED_THRESHOLD = 5
EVIDENCE_SCATTER_CHAPTER_THRESHOLD = 5
EVIDENCE_SCATTER_BOOK_THRESHOLD = 3

DEFINITION_INTENT_PHRASES = (
    "what is",
    "define",
    "overview",
    "introduce",
    "什么是",
    "是什么",
    "概览",
    "简单介绍",
    "简要说明",
)


def default_term_user_query(term: str) -> str:
    return f'Explain the term "{term}" using the retrieved cluster.'


def evaluate_term_retrieval_quality(
    *,
    term: str,
    user_query: str,
    user_query_was_default: bool,
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
) -> dict[str, object] | None:
    _ = term
    seed_count = _seed_count(cluster)
    evidence_bullet_chapter_count, evidence_book_count = _evidence_spread(
        cluster=cluster,
        evidence=evidence,
    )

    term_too_broad = seed_count >= TERM_TOO_BROAD_SEED_THRESHOLD
    evidence_too_scattered = (
        evidence_bullet_chapter_count >= EVIDENCE_SCATTER_CHAPTER_THRESHOLD
        or evidence_book_count >= EVIDENCE_SCATTER_BOOK_THRESHOLD
    )

    if not term_too_broad and not evidence_too_scattered:
        return None

    definition_intent = not user_query_was_default and _is_definition_intent(user_query)
    state = "broad_allowed" if definition_intent else "broad_blocked"

    result: dict[str, object] = {
        "state": state,
        "term_too_broad": term_too_broad,
        "evidence_too_scattered": evidence_too_scattered,
        "seed_count": seed_count,
        "seed_threshold": TERM_TOO_BROAD_SEED_THRESHOLD,
        "evidence_bullet_chapter_count": evidence_bullet_chapter_count,
        "evidence_book_count": evidence_book_count,
        "evidence_chapter_threshold": EVIDENCE_SCATTER_CHAPTER_THRESHOLD,
        "evidence_book_threshold": EVIDENCE_SCATTER_BOOK_THRESHOLD,
    }

    if state == "broad_allowed":
        result["message"] = (
            "This term is broad, so the answer is limited to a high-level overview."
        )
    else:
        result["message"] = (
            "This term is too broad for a precise answer. Please narrow it."
        )
    return result


def broad_overview_prompt_note(suggested_terms: Iterable[str]) -> str:
    joined = ", ".join(suggested_terms)
    if joined:
        return (
            "Warning: retrieval is broad. Give only a concise high-level concept "
            "explanation. Do not provide detailed analysis. Recommend narrower "
            f"follow-up terms such as: {joined}."
        )
    return (
        "Warning: retrieval is broad. Give only a concise high-level concept "
        "explanation. Do not provide detailed analysis. Recommend narrower "
        "follow-up terms."
    )


def _seed_count(cluster: dict[str, object]) -> int:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return 0
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return 0
    return sum(1 for seed_id in seed_ids if isinstance(seed_id, str))


def _evidence_spread(
    *,
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
) -> tuple[int, int]:
    chapter_to_book: dict[str, str] = {}
    chapters = cluster.get("chapters")
    if isinstance(chapters, list):
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            chapter_id = chapter.get("chapter_id")
            book_id = chapter.get("book_id")
            if isinstance(chapter_id, str) and isinstance(book_id, str):
                chapter_to_book[chapter_id] = book_id

    bullet_chapter_ids: set[str] = set()
    book_ids: set[str] = set()
    bullets = evidence.get("bullets") if isinstance(evidence, dict) else None
    if isinstance(bullets, list):
        for bullet in bullets:
            if not isinstance(bullet, dict):
                continue
            chapter_id = bullet.get("chapter_id")
            if not isinstance(chapter_id, str):
                continue
            bullet_chapter_ids.add(chapter_id)
            book_id = chapter_to_book.get(chapter_id)
            if isinstance(book_id, str):
                book_ids.add(book_id)

    return len(bullet_chapter_ids), len(book_ids)


def _is_definition_intent(user_query: str) -> bool:
    normalized = " ".join(user_query.strip().lower().split())
    if not normalized:
        return False
    return any(phrase in normalized for phrase in DEFINITION_INTENT_PHRASES)
