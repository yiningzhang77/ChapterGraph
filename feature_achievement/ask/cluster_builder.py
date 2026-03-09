from collections import OrderedDict
import re

from fastapi import HTTPException
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.db.ask_queries import (
    get_edges_from_sources,
    get_enriched_by_ids,
    get_run,
    resolve_chapter_seed_id,
    search_term_seed_ids_ilike,
)


def _truncate_text(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _normalize_text(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _score_text(query_tokens: set[str], candidate: str) -> float:
    if not query_tokens:
        return 0.0
    candidate_tokens = set(_normalize_text(candidate).split())
    if not candidate_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(candidate_tokens))
    return overlap / len(query_tokens)


def _pick_seed_ids(session: Session, req: AskRequest) -> tuple[list[str], str]:
    if req.query_type == "chapter":
        chapter_ref = req.chapter_id or req.query
        chapter_id = resolve_chapter_seed_id(
            session=session,
            chapter_ref=chapter_ref,
            enrichment_version=req.enrichment_version,
        )
        if chapter_id is None:
            return [], "chapter_not_found"
        return [chapter_id], "chapter_selected"

    term_ids = search_term_seed_ids_ilike(
        session=session,
        term=req.query,
        enrichment_version=req.enrichment_version,
        limit=req.seed_top_k,
    )
    return term_ids, "term_ilike"


def _section_title(section: dict[str, object]) -> str:
    title_norm = section.get("title_norm")
    if isinstance(title_norm, str) and title_norm.strip():
        return title_norm
    title_raw = section.get("title_raw")
    if isinstance(title_raw, str):
        return title_raw
    return ""


def _build_evidence(chapters: list[dict[str, object]], req: AskRequest) -> dict[str, object]:
    query_tokens = set(_normalize_text(req.query).split())
    section_rows: list[dict[str, object]] = []
    bullet_rows: list[dict[str, object]] = []

    for chapter in chapters:
        chapter_id = chapter.get("chapter_id")
        sections_value = chapter.get("sections")
        if not isinstance(chapter_id, str) or not isinstance(sections_value, list):
            continue

        for section in sections_value:
            if not isinstance(section, dict):
                continue

            section_id = section.get("section_id")
            if not isinstance(section_id, str):
                continue

            section_title = _section_title(section)
            section_score = _score_text(query_tokens, section_title)

            bullets_value = section.get("bullets")
            bullet_max_score = 0.0
            if isinstance(bullets_value, list):
                for bullet in bullets_value:
                    if not isinstance(bullet, dict):
                        continue
                    bullet_id = bullet.get("bullet_id")
                    if not isinstance(bullet_id, str):
                        continue

                    text_norm = bullet.get("text_norm")
                    text_raw = bullet.get("text_raw")
                    bullet_text = text_norm if isinstance(text_norm, str) else (
                        text_raw if isinstance(text_raw, str) else ""
                    )
                    score = _score_text(query_tokens, bullet_text)
                    if score > bullet_max_score:
                        bullet_max_score = score

                    source_refs = bullet.get("source_refs")
                    if source_refs is not None and not isinstance(source_refs, list):
                        source_refs = None

                    bullet_rows.append(
                        {
                            "chapter_id": chapter_id,
                            "section_id": section_id,
                            "bullet_id": bullet_id,
                            "text_norm": text_norm,
                            "text_raw": text_raw,
                            "score": score,
                            "source_refs": source_refs,
                        }
                    )

            combined_score = section_score * 0.7 + bullet_max_score * 0.3
            section_rows.append(
                {
                    "chapter_id": chapter_id,
                    "section_id": section_id,
                    "title_norm": section.get("title_norm"),
                    "title_raw": section.get("title_raw"),
                    "score": combined_score,
                }
            )

    section_rows.sort(
        key=lambda row: (
            -float(row.get("score", 0.0)),
            str(row.get("chapter_id", "")),
            str(row.get("section_id", "")),
        )
    )
    bullet_rows.sort(
        key=lambda row: (
            -float(row.get("score", 0.0)),
            str(row.get("chapter_id", "")),
            str(row.get("section_id", "")),
            str(row.get("bullet_id", "")),
        )
    )

    return {
        "sections": section_rows[: req.section_top_k],
        "bullets": bullet_rows[: req.bullet_top_k],
    }


def build_cluster(session: Session, req: AskRequest) -> dict[str, object]:
    run = get_run(session, req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.enrichment_version != req.enrichment_version:
        raise HTTPException(
            status_code=409,
            detail=(
                "run.enrichment_version does not match request enrichment_version: "
                f"{run.enrichment_version} != {req.enrichment_version}"
            ),
        )

    seed_ids, seed_reason = _pick_seed_ids(session, req)
    if not seed_ids:
        raise HTTPException(status_code=422, detail="No seed chapters found")

    chapter_ids: OrderedDict[str, bool] = OrderedDict((seed_id, True) for seed_id in seed_ids)
    cluster_edges: list[dict[str, object]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    frontier = set(seed_ids)

    for _ in range(req.max_hops):
        if not frontier:
            break
        edges = get_edges_from_sources(
            session=session,
            run_id=req.run_id,
            source_ids=frontier,
            min_edge_score=req.min_edge_score,
            limit=req.neighbor_top_k,
        )
        next_frontier: set[str] = set()

        for edge in edges:
            edge_key = (edge.from_chapter, edge.to_chapter, edge.type)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            cluster_edges.append(
                {
                    "from": edge.from_chapter,
                    "to": edge.to_chapter,
                    "score": edge.score,
                    "type": edge.type,
                }
            )
            if edge.to_chapter not in chapter_ids:
                chapter_ids[edge.to_chapter] = True
                next_frontier.add(edge.to_chapter)
        frontier = next_frontier

    ordered_ids = list(chapter_ids.keys())
    rows = get_enriched_by_ids(
        session=session,
        chapter_ids=ordered_ids,
        enrichment_version=req.enrichment_version,
    )
    row_by_id = {row.id: row for row in rows}

    chapters: list[dict[str, object]] = []
    for chapter_id in ordered_ids:
        row = row_by_id.get(chapter_id)
        if row is None:
            continue

        chapters.append(
            {
                "chapter_id": row.id,
                "book_id": row.book_id,
                "title": row.title,
                "chapter_text": _truncate_text(row.chapter_text or ""),
                "chapter_index_text": _truncate_text(row.chapter_index_text or ""),
                "sections": row.sections,
            }
        )

    visible_ids = {
        chapter["chapter_id"]
        for chapter in chapters
        if isinstance(chapter.get("chapter_id"), str)
    }
    filtered_edges = [
        edge
        for edge in cluster_edges
        if isinstance(edge.get("from"), str)
        and isinstance(edge.get("to"), str)
        and edge["from"] in visible_ids
        and edge["to"] in visible_ids
    ]

    evidence = _build_evidence(chapters, req)

    chapter_payload = [
        {
            "chapter_id": chapter["chapter_id"],
            "book_id": chapter["book_id"],
            "title": chapter["title"],
            "chapter_text": chapter["chapter_text"],
            "chapter_index_text": chapter["chapter_index_text"],
        }
        for chapter in chapters
    ]

    return {
        "schema_version": "cluster.v1",
        "query": req.query,
        "query_type": req.query_type,
        "run_id": req.run_id,
        "enrichment_version": req.enrichment_version,
        "seed": {
            "seed_chapter_ids": seed_ids,
            "seed_reason": seed_reason,
        },
        "chapters": chapter_payload,
        "edges": filtered_edges,
        "evidence": evidence,
        "constraints": {
            "max_hops": req.max_hops,
            "seed_top_k": req.seed_top_k,
            "neighbor_top_k": req.neighbor_top_k,
            "min_edge_score": req.min_edge_score,
            "section_top_k": req.section_top_k,
            "bullet_top_k": req.bullet_top_k,
        },
    }
