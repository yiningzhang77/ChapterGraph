from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import chapter_tools
from feature_achievement.ask.tool_contracts import ChapterClusterToolResult, TermAnswerToolResult


def test_build_chapter_cluster_tool_returns_typed_contract(monkeypatch) -> None:
    req = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        chapter_tools,
        "build_cluster",
        lambda **kwargs: {
            "schema_version": "cluster.v1",
            "seed": {"seed_chapter_ids": ["spring::ch2"]},
            "chapters": [{"chapter_id": "spring::ch2"}],
            "edges": [],
            "evidence": {"bullets": [{"chapter_id": "spring::ch2"}]},
        },
    )

    result = chapter_tools.build_chapter_cluster_tool(
        req=req,
        session=cast(Session, object()),
    )

    assert result == ChapterClusterToolResult(
        chapter_id="spring::ch2",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        cluster={
            "schema_version": "cluster.v1",
            "seed": {"seed_chapter_ids": ["spring::ch2"]},
            "chapters": [{"chapter_id": "spring::ch2"}],
            "edges": [],
        },
        evidence={"bullets": [{"chapter_id": "spring::ch2"}]},
        seed_ids=["spring::ch2"],
    )


def test_generate_chapter_answer_tool_returns_typed_answer_result(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_ask_qwen(**kwargs: object) -> str:
        captured.update(kwargs)
        return "chapter answer"

    monkeypatch.setattr(chapter_tools, "ask_qwen", fake_ask_qwen)

    result = chapter_tools.generate_chapter_answer_tool(
        query="Explain selected chapter",
        cluster={"chapters": []},
        llm_enabled=True,
        llm_model=None,
        llm_timeout_ms=30000,
    )

    assert result == TermAnswerToolResult(
        answer_markdown="chapter answer",
        llm_error=None,
    )
    assert captured["query_type"] == "chapter"
    assert captured["retrieval_term"] is None


def test_generate_chapter_answer_tool_returns_typed_error_result(monkeypatch) -> None:
    monkeypatch.setattr(
        chapter_tools,
        "ask_qwen",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("llm failure")),
    )

    result = chapter_tools.generate_chapter_answer_tool(
        query="Explain selected chapter",
        cluster={"chapters": []},
        llm_enabled=True,
        llm_model=None,
        llm_timeout_ms=30000,
    )

    assert result == TermAnswerToolResult(
        answer_markdown=None,
        llm_error="llm failure",
    )
