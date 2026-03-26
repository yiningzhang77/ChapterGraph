import json
import logging
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.runtime import run_runtime
from feature_achievement.ask.runtime_adapter import to_runtime_request
from feature_achievement.ask.tool_contracts import RUNTIME_STATE_NORMAL
from feature_achievement.db.engine import get_session

router = APIRouter(prefix="", tags=["ask"])
AUDIT_LOGGER = logging.getLogger("uvicorn.error")


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


def _request_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    client = request.client
    if client is None:
        return None
    return client.host


def _emit_ask_audit_log(
    *,
    request: Request,
    req: AskRequest,
    duration_ms: int,
    outcome: str,
    response_state: str | None = None,
    http_status: int = 200,
    llm_error: str | None = None,
    error_detail: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "path": "/ask",
        "ip": _request_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "query_type": req.query_type,
        "term": req.term,
        "chapter_id": req.chapter_id,
        "query": req.query,
        "run_id": req.run_id,
        "enrichment_version": req.enrichment_version,
        "llm_enabled": req.llm_enabled,
        "llm_timeout_ms": req.llm_timeout_ms,
        "outcome": outcome,
        "http_status": http_status,
        "duration_ms": duration_ms,
    }
    if response_state:
        payload["response_state"] = response_state
    if llm_error:
        payload["llm_error"] = llm_error
    if error_detail:
        payload["error_detail"] = error_detail
    AUDIT_LOGGER.info("ask_audit %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    started_at = perf_counter()
    try:
        runtime_request = to_runtime_request(req)
        runtime_result = run_runtime(request=runtime_request, session=session)

        final_state = runtime_result.final_state
        cluster_payload = final_state.get("cluster_payload")
        evidence = final_state.get("evidence")
        retrieval_warnings = final_state.get("retrieval_warnings")
        llm_error = final_state.get("llm_error")
        runtime_state = runtime_result.runtime_state
        answer_markdown = runtime_result.answer_markdown

        if not isinstance(cluster_payload, dict):
            cluster_payload = {"schema_version": "cluster.v1", "chapters": [], "edges": []}
        if evidence is not None and not isinstance(evidence, dict):
            evidence = None
        if retrieval_warnings is not None and not isinstance(retrieval_warnings, dict):
            retrieval_warnings = None
        if llm_error is not None and not isinstance(llm_error, str):
            llm_error = None

        graph_fragment = (
            _build_graph_fragment(cluster_payload) if req.return_graph_fragment else None
        )

        meta: dict[str, object] = {"schema_version": "cluster.v1"}
        if runtime_state != RUNTIME_STATE_NORMAL:
            meta["response_state"] = runtime_state
        if retrieval_warnings:
            meta["retrieval_warnings"] = retrieval_warnings
        if llm_error:
            meta["llm_error"] = llm_error

        response = AskResponse(
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
        _emit_ask_audit_log(
            request=request,
            req=req,
            duration_ms=round((perf_counter() - started_at) * 1000),
            outcome="ok",
            response_state=runtime_state if runtime_state != RUNTIME_STATE_NORMAL else None,
            llm_error=llm_error,
        )
        return response
    except HTTPException as exc:
        _emit_ask_audit_log(
            request=request,
            req=req,
            duration_ms=round((perf_counter() - started_at) * 1000),
            outcome="http_error",
            http_status=exc.status_code,
            error_detail=str(exc.detail),
        )
        raise
    except Exception as exc:
        _emit_ask_audit_log(
            request=request,
            req=req,
            duration_ms=round((perf_counter() - started_at) * 1000),
            outcome="error",
            http_status=500,
            error_detail=str(exc),
        )
        raise
