from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.term_flow import run_term_flow
from feature_achievement.db.engine import get_session
from feature_achievement.llm.qwen_client import ask_qwen

router = APIRouter(prefix="", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    session: Session = Depends(get_session),
):
    if req.query_type == "term":
        term_flow_result = run_term_flow(req=req, session=session)
        cluster_payload = term_flow_result.get("cluster_payload")
        if not isinstance(cluster_payload, dict):
            cluster_payload = {}
        evidence = (
            term_flow_result.get("evidence")
            if isinstance(term_flow_result.get("evidence"), dict)
            else None
        )
        retrieval_warnings = (
            term_flow_result.get("retrieval_warnings")
            if isinstance(term_flow_result.get("retrieval_warnings"), dict)
            else None
        )
        response_state = (
            term_flow_result.get("response_state")
            if isinstance(term_flow_result.get("response_state"), str)
            else None
        )
        response_guidance = (
            term_flow_result.get("response_guidance")
            if isinstance(term_flow_result.get("response_guidance"), str)
            else None
        )
        answer_markdown = (
            term_flow_result.get("answer_markdown")
            if isinstance(term_flow_result.get("answer_markdown"), str)
            else None
        )
        llm_error = (
            term_flow_result.get("llm_error")
            if isinstance(term_flow_result.get("llm_error"), str)
            else None
        )
    else:
        cluster = build_cluster(session=session, req=req)
        evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
        cluster_payload = dict(cluster)
        cluster_payload.pop("evidence", None)
        retrieval_warnings = None
        response_state = None
        response_guidance = None
        answer_markdown = None
        llm_error = None

    if req.query_type == "term":
        pass
    elif req.llm_enabled:
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
