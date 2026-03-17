from __future__ import annotations

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.ask.tool_contracts import ChapterClusterToolResult, TermAnswerToolResult
from feature_achievement.llm.qwen_client import ask_qwen


def build_chapter_cluster_tool(
    *,
    req: AskRequest,
    session: Session,
) -> ChapterClusterToolResult:
    cluster = build_cluster(session=session, req=req)
    evidence = cluster.get("evidence") if isinstance(cluster.get("evidence"), dict) else None
    cluster_payload = dict(cluster)
    cluster_payload.pop("evidence", None)
    return ChapterClusterToolResult(
        chapter_id=req.chapter_id or "",
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        cluster=cluster_payload,
        evidence=evidence,
        seed_ids=_seed_ids_from_cluster(cluster_payload),
    )


def generate_chapter_answer_tool(
    *,
    query: str,
    cluster: dict[str, object],
    llm_enabled: bool,
    llm_model: str | None,
    llm_timeout_ms: int,
) -> TermAnswerToolResult:
    if not llm_enabled:
        return TermAnswerToolResult(answer_markdown=None, llm_error=None)

    try:
        answer_markdown = ask_qwen(
            query=query,
            query_type="chapter",
            cluster=cluster,
            retrieval_term=None,
            response_guidance=None,
            model=llm_model,
            timeout_ms=llm_timeout_ms,
        )
    except Exception as error:
        return TermAnswerToolResult(
            answer_markdown=None,
            llm_error=str(error),
        )

    return TermAnswerToolResult(
        answer_markdown=answer_markdown,
        llm_error=None,
    )


def _seed_ids_from_cluster(cluster: dict[str, object]) -> list[str]:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return []
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return []
    return [seed_id for seed_id in seed_ids if isinstance(seed_id, str)]
