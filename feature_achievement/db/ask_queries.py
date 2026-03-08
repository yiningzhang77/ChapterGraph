from collections.abc import Iterable

from sqlalchemy import or_
from sqlmodel import Session, select

from feature_achievement.db.models import Edge, EnrichedChapter, Run


def get_run(session: Session, run_id: int) -> Run | None:
    return session.get(Run, run_id)


def search_term_seed_ids_ilike(
    session: Session,
    term: str,
    enrichment_version: str,
    limit: int,
) -> list[str]:
    pattern = f"%{term}%"
    stmt = (
        select(EnrichedChapter.id)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(
            or_(
                EnrichedChapter.chapter_text.ilike(pattern),
                EnrichedChapter.title.ilike(pattern),
            )
        )
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return [row for row in rows if isinstance(row, str)]


def resolve_chapter_seed_id(
    session: Session,
    chapter_ref: str,
    enrichment_version: str,
) -> str | None:
    exact_stmt = (
        select(EnrichedChapter.id)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.id == chapter_ref)
    )
    exact = session.exec(exact_stmt).first()
    if isinstance(exact, str):
        return exact

    title_stmt = (
        select(EnrichedChapter.id)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.title.ilike(f"%{chapter_ref}%"))
        .limit(1)
    )
    title_match = session.exec(title_stmt).first()
    if isinstance(title_match, str):
        return title_match
    return None


def get_edges_from_sources(
    session: Session,
    run_id: int,
    source_ids: Iterable[str],
    min_edge_score: float,
    limit: int,
) -> list[Edge]:
    source_list = list(source_ids)
    if not source_list:
        return []
    stmt = (
        select(Edge)
        .where(Edge.run_id == run_id)
        .where(Edge.from_chapter.in_(source_list))
        .where(Edge.score >= min_edge_score)
        .order_by(Edge.score.desc())
        .limit(limit)
    )
    return session.exec(stmt).all()


def get_enriched_by_ids(
    session: Session,
    chapter_ids: Iterable[str],
    enrichment_version: str,
) -> list[EnrichedChapter]:
    chapter_list = list(chapter_ids)
    if not chapter_list:
        return []
    stmt = (
        select(EnrichedChapter)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.id.in_(chapter_list))
    )
    return session.exec(stmt).all()

