from collections import OrderedDict

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
        "chapters": chapters,
        "edges": filtered_edges,
        "constraints": {
            "max_hops": req.max_hops,
            "seed_top_k": req.seed_top_k,
            "neighbor_top_k": req.neighbor_top_k,
            "min_edge_score": req.min_edge_score,
        },
    }
