from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.chapter_tools import (
    build_chapter_cluster_tool,
    generate_chapter_answer_tool,
)
from feature_achievement.ask.tool_contracts import ChapterClusterToolResult


def run_chapter_flow(
    *,
    req: AskRequest,
    session: Session,
) -> dict[str, object]:
    cluster_result = _build_chapter_cluster(req=req, session=session)
    answer_result = _generate_chapter_answer(req=req, cluster_result=cluster_result)
    return {
        "cluster_payload": cluster_result.cluster,
        "evidence": cluster_result.evidence,
        "retrieval_warnings": None,
        "response_state": None,
        "response_guidance": None,
        "answer_markdown": answer_result["answer_markdown"],
        "llm_error": answer_result["llm_error"],
    }


def _build_chapter_cluster(
    *,
    req: AskRequest,
    session: Session,
) -> ChapterClusterToolResult:
    return build_chapter_cluster_tool(req=req, session=session)


def _generate_chapter_answer(
    *,
    req: AskRequest,
    cluster_result: ChapterClusterToolResult,
) -> dict[str, object]:
    answer_result = generate_chapter_answer_tool(
        query=req.query or "",
        cluster=cluster_result.cluster,
        llm_enabled=req.llm_enabled,
        llm_model=req.llm_model,
        llm_timeout_ms=req.llm_timeout_ms,
    )
    return {
        "answer_markdown": answer_result.answer_markdown,
        "llm_error": answer_result.llm_error,
    }
