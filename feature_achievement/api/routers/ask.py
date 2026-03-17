from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.chapter_flow import run_chapter_flow
from feature_achievement.ask.term_flow import run_term_flow
from feature_achievement.ask.tool_contracts import ChapterFlowResult, TermFlowResult
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


def _run_term_request(
    *,
    req: AskRequest,
    session: Session,
) -> TermFlowResult:
    return run_term_flow(req=req, session=session)


def _run_chapter_request(
    *,
    req: AskRequest,
    session: Session,
) -> ChapterFlowResult:
    return run_chapter_flow(req=req, session=session)


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    session: Session = Depends(get_session),
):
    if req.query_type == "term":
        request_result = _run_term_request(req=req, session=session)
    else:
        request_result = _run_chapter_request(req=req, session=session)

    cluster_payload = request_result.cluster_payload
    evidence = request_result.evidence
    retrieval_warnings = request_result.retrieval_warnings
    response_state = request_result.response_state
    answer_markdown = request_result.answer_markdown
    llm_error = request_result.llm_error

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
