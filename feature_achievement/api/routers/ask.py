from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.term_flow import run_term_flow
from feature_achievement.db.engine import get_session
from feature_achievement.llm.qwen_client import ask_qwen

router = APIRouter(prefix="", tags=["ask"])


def _coerce_term_flow_result(result: dict[str, object]) -> dict[str, object]:
    cluster_payload = result.get("cluster_payload")
    return {
        "cluster_payload": cluster_payload if isinstance(cluster_payload, dict) else {},
        "evidence": result.get("evidence")
        if isinstance(result.get("evidence"), dict)
        else None,
        "retrieval_warnings": result.get("retrieval_warnings")
        if isinstance(result.get("retrieval_warnings"), dict)
        else None,
        "response_state": result.get("response_state")
        if isinstance(result.get("response_state"), str)
        else None,
        "response_guidance": result.get("response_guidance")
        if isinstance(result.get("response_guidance"), str)
        else None,
        "answer_markdown": result.get("answer_markdown")
        if isinstance(result.get("answer_markdown"), str)
        else None,
        "llm_error": result.get("llm_error")
        if isinstance(result.get("llm_error"), str)
        else None,
    }


def _build_graph_fragment(cluster_payload: dict[str, object]) -> dict[str, object]:
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

    return {
        "nodes": nodes,
        "edges": edges,
    }


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    session: Session = Depends(get_session),
):
    if req.query_type == "term":
        term_result = _coerce_term_flow_result(run_term_flow(req=req, session=session))
        cluster_payload = term_result["cluster_payload"]
        evidence = term_result["evidence"]
        retrieval_warnings = term_result["retrieval_warnings"]
        response_state = term_result["response_state"]
        answer_markdown = term_result["answer_markdown"]
        llm_error = term_result["llm_error"]
    else:
        cluster = build_cluster(session=session, req=req)
        evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
        cluster_payload = dict(cluster)
        cluster_payload.pop("evidence", None)
        retrieval_warnings = None
        response_state = None
        answer_markdown = None
        llm_error = None

    if req.query_type == "chapter" and req.llm_enabled:
        if response_state != "needs_narrower_term":
            try:
                answer_markdown = ask_qwen(
                    query=req.query or "",
                    query_type=req.query_type,
                    cluster=cluster_payload,
                    retrieval_term=None,
                    response_guidance=None,
                    model=req.llm_model,
                    timeout_ms=req.llm_timeout_ms,
                )
            except Exception as error:
                llm_error = str(error)

    graph_fragment = (
        _build_graph_fragment(cluster_payload) if req.return_graph_fragment else None
    )

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
