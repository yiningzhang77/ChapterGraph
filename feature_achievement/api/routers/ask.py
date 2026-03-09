from fastapi import APIRouter, Depends
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.ask.cluster_builder import build_cluster
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
    if req.llm_enabled:
        try:
            answer_markdown = ask_qwen(
                query=req.query,
                query_type=req.query_type,
                cluster=cluster_payload,
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
