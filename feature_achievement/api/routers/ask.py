from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.candidate_anchor import rank_candidate_anchors
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.retrieval_quality import (
    broad_overview_prompt_note,
    default_term_user_query,
    evaluate_term_retrieval_quality,
)
from feature_achievement.ask.term_recommender import recommend_narrower_terms
from feature_achievement.db.engine import get_session
from feature_achievement.llm.qwen_client import ask_qwen

router = APIRouter(prefix="", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    session: Session = Depends(get_session),
):
    cluster = build_cluster(session=session, req=req)
    evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
    cluster_payload = dict(cluster)
    cluster_payload.pop("evidence", None)
    answer_markdown: str | None = None
    llm_error: str | None = None
    response_guidance: str | None = None
    response_state: str | None = None

    retrieval_warnings: dict[str, object] | None = None
    if req.query_type == "term":
        term = req.term or ""
        user_query = req.user_query or default_term_user_query(term)
        retrieval_warnings = evaluate_term_retrieval_quality(
            term=term,
            user_query=user_query,
            user_query_was_default=user_query == default_term_user_query(term),
            cluster=cluster_payload,
            evidence=evidence,
        )
        if isinstance(retrieval_warnings, dict):
            recommendation = recommend_narrower_terms(
                broad_term=term,
                user_query=user_query,
            )
            suggested_terms = recommendation.get("suggested_terms")
            if isinstance(suggested_terms, list):
                filtered_suggested_terms = [
                    value for value in suggested_terms if isinstance(value, str)
                ]
                state = retrieval_warnings.get("state")
                if state == "broad_blocked" and filtered_suggested_terms:
                    try:
                        ranked_candidates = rank_candidate_anchors(
                            terms=filtered_suggested_terms,
                            user_query=user_query,
                            run_id=req.run_id,
                            enrichment_version=req.enrichment_version,
                            session=session,
                        )
                    except Exception:
                        ranked_candidates = []
                    ranked_terms = [
                        candidate.get("term")
                        for candidate in ranked_candidates
                        if isinstance(candidate, dict)
                        and isinstance(candidate.get("term"), str)
                    ]
                    if ranked_terms:
                        filtered_suggested_terms = ranked_terms
                suggested_terms = filtered_suggested_terms
                retrieval_warnings["suggested_terms"] = filtered_suggested_terms
            recommendation_reason = recommendation.get("reason")
            if isinstance(recommendation_reason, str):
                retrieval_warnings["recommendation_reason"] = recommendation_reason
            recommendation_source = recommendation.get("source")
            if isinstance(recommendation_source, str):
                retrieval_warnings["recommendation_source"] = recommendation_source
            recommendation_confidence = recommendation.get("confidence")
            if isinstance(recommendation_confidence, str):
                retrieval_warnings["recommendation_confidence"] = (
                    recommendation_confidence
                )
            state = retrieval_warnings.get("state")
            if state == "broad_blocked":
                response_state = "needs_narrower_term"
            elif state == "broad_allowed":
                response_state = "broad_overview"
                response_guidance = broad_overview_prompt_note(
                    suggested_terms if isinstance(suggested_terms, list) else []
                )

    if req.llm_enabled:
        if response_state != "needs_narrower_term":
            try:
                answer_markdown = ask_qwen(
                    query=req.user_query if req.query_type == "term" else req.query or "",
                    query_type=req.query_type,
                    cluster=cluster_payload,
                    retrieval_term=req.term if req.query_type == "term" else None,
                    response_guidance=response_guidance,
                    model=req.llm_model,
                    timeout_ms=req.llm_timeout_ms,
                )
            except Exception as error:
                llm_error = str(error)

    graph_fragment: dict[str, object] | None = None
    if req.return_graph_fragment:
        chapter_entries = cluster_payload.get("chapters")
        edge_entries = cluster_payload.get("edges")

        nodes: list[dict[str, object]] = []
        if isinstance(chapter_entries, list):
            for entry in chapter_entries:
                if not isinstance(entry, dict):
                    continue
                chapter_id = entry.get("chapter_id")
                book_id = entry.get("book_id")
                title = entry.get("title")
                if not isinstance(chapter_id, str) or not isinstance(book_id, str):
                    continue
                nodes.append(
                    {
                        "id": chapter_id,
                        "book_id": book_id,
                        "title": title,
                    }
                )

        edges: list[dict[str, object]] = []
        if isinstance(edge_entries, list):
            for entry in edge_entries:
                if not isinstance(entry, dict):
                    continue
                source = entry.get("from")
                target = entry.get("to")
                if not isinstance(source, str) or not isinstance(target, str):
                    continue
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "score": entry.get("score"),
                        "type": entry.get("type"),
                    }
                )

        graph_fragment = {
            "nodes": nodes,
            "edges": edges,
        }

    meta: dict[str, object] = {"schema_version": "cluster.v1"}
    if response_state:
        meta["response_state"] = response_state
    if retrieval_warnings:
        meta["retrieval_warnings"] = retrieval_warnings
    if llm_error:
        meta["llm_error"] = llm_error

    return AskResponse(
        query=req.query,
        query_type=req.query_type,
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        answer_markdown=answer_markdown,
        cluster=cluster_payload if req.return_cluster else None,
        evidence=evidence,
        graph_fragment=graph_fragment,
        meta=meta,
    )
