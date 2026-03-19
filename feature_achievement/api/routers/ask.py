from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.runtime import run_runtime
from feature_achievement.ask.runtime_adapter import to_runtime_request
from feature_achievement.ask.tool_contracts import RUNTIME_STATE_NORMAL
from feature_achievement.db.engine import get_session

router = APIRouter(prefix="", tags=["ask"])


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
