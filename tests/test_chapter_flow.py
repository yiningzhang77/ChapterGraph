from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import chapter_flow
from feature_achievement.ask.tool_contracts import (
    ChapterClusterToolResult,
    ChapterFlowResult,
    TermAnswerToolResult,
)


def _cluster_result() -> ChapterClusterToolResult:
    return ChapterClusterToolResult(
        chapter_id="spring::ch2",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        cluster={"chapters": [], "edges": [], "seed": {"seed_chapter_ids": ["spring::ch2"]}},
        evidence={"bullets": []},
        seed_ids=["spring::ch2"],
    )


def test_run_chapter_flow_returns_service_shape(monkeypatch) -> None:
    req = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(chapter_flow, "_build_chapter_cluster", lambda **kwargs: _cluster_result())
    monkeypatch.setattr(
        chapter_flow,
        "_generate_chapter_answer",
        lambda **kwargs: {
            "answer_markdown": "chapter answer",
            "llm_error": None,
        },
    )

    result = chapter_flow.run_chapter_flow(
        req=req,
        session=cast(Session, object()),
    )

    assert result == ChapterFlowResult(
        cluster_payload={
            "chapters": [],
            "edges": [],
            "seed": {"seed_chapter_ids": ["spring::ch2"]},
        },
        evidence={"bullets": []},
        retrieval_warnings=None,
        response_state=None,
        response_guidance=None,
        answer_markdown="chapter answer",
        llm_error=None,
    )


def test_generate_chapter_answer_uses_wrapper(monkeypatch) -> None:
    req = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        query="Explain selected chapter",
        run_id=5,
        llm_enabled=True,
    )
    captured: dict[str, object] = {}

    def fake_generate_chapter_answer_tool(**kwargs: object) -> TermAnswerToolResult:
        captured.update(kwargs)
        return TermAnswerToolResult(
            answer_markdown="chapter answer",
            llm_error=None,
        )

    monkeypatch.setattr(
        chapter_flow,
        "generate_chapter_answer_tool",
        fake_generate_chapter_answer_tool,
    )

    result = chapter_flow._generate_chapter_answer(
        req=req,
        cluster_result=_cluster_result(),
    )

    assert result == {
        "answer_markdown": "chapter answer",
        "llm_error": None,
    }
    assert captured["query"] == "Explain selected chapter"
    assert captured["cluster"] == {"chapters": [], "edges": [], "seed": {"seed_chapter_ids": ["spring::ch2"]}}


def test_generate_chapter_answer_preserves_llm_error(monkeypatch) -> None:
    req = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        query="Explain selected chapter",
        run_id=5,
        llm_enabled=True,
    )

    monkeypatch.setattr(
        chapter_flow,
        "generate_chapter_answer_tool",
        lambda **kwargs: TermAnswerToolResult(
            answer_markdown=None,
            llm_error="llm failure",
        ),
    )

    result = chapter_flow._generate_chapter_answer(
        req=req,
        cluster_result=_cluster_result(),
    )

    assert result == {
        "answer_markdown": None,
        "llm_error": "llm failure",
    }
