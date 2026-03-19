from __future__ import annotations

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import runtime
from feature_achievement.ask.runtime_adapter import to_runtime_request
from feature_achievement.ask.tool_contracts import (
    ChapterFlowResult,
    RUNTIME_STATE_NEEDS_NARROWER_TERM,
    RUNTIME_STATE_NORMAL,
    TermFlowResult,
)


class DummySession:
    pass


def test_run_runtime_dispatches_term_requests(
    monkeypatch,
) -> None:
    expected_request = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
        return_cluster=True,
        return_graph_fragment=False,
    )
    runtime_request = to_runtime_request(expected_request)

    def fake_run_term_flow(*, req: AskRequest, session: DummySession) -> TermFlowResult:
        assert req == expected_request
        assert isinstance(session, DummySession)
        return TermFlowResult(
            cluster_payload={"schema_version": "cluster.v1"},
            evidence={"sections": [], "bullets": []},
            retrieval_warnings=None,
            runtime_state=RUNTIME_STATE_NORMAL,
            response_guidance=None,
            answer_markdown="answer",
            llm_error=None,
        )

    monkeypatch.setattr(runtime, "run_term_flow", fake_run_term_flow)

    result = runtime.run_runtime(request=runtime_request, session=DummySession())

    assert result.status == "completed"
    assert result.answer_markdown == "answer"
    assert result.runtime_state == RUNTIME_STATE_NORMAL
    assert result.final_state["cluster_payload"] == {"schema_version": "cluster.v1"}
    assert result.events == [
        {"type": "term_flow_completed", "runtime_state": RUNTIME_STATE_NORMAL}
    ]


def test_run_runtime_dispatches_chapter_requests(
    monkeypatch,
) -> None:
    expected_request = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        query="Explain selected chapter",
        run_id=7,
        llm_enabled=False,
        return_cluster=False,
        return_graph_fragment=True,
    )
    runtime_request = to_runtime_request(expected_request)

    def fake_run_chapter_flow(
        *,
        req: AskRequest,
        session: DummySession,
    ) -> ChapterFlowResult:
        assert req == expected_request
        assert isinstance(session, DummySession)
        return ChapterFlowResult(
            cluster_payload={"schema_version": "cluster.v1"},
            evidence={"sections": [], "bullets": []},
            retrieval_warnings=None,
            runtime_state=RUNTIME_STATE_NORMAL,
            response_guidance=None,
            answer_markdown=None,
            llm_error=None,
        )

    monkeypatch.setattr(runtime, "run_chapter_flow", fake_run_chapter_flow)

    result = runtime.run_runtime(request=runtime_request, session=DummySession())

    assert result.status == "completed"
    assert result.answer_markdown is None
    assert result.runtime_state == RUNTIME_STATE_NORMAL
    assert result.final_state["cluster_payload"] == {"schema_version": "cluster.v1"}
    assert result.events == [
        {"type": "chapter_flow_completed", "runtime_state": RUNTIME_STATE_NORMAL}
    ]


def test_run_runtime_maps_blocked_term_state_to_blocked_execution(
    monkeypatch,
) -> None:
    runtime_request = to_runtime_request(
        AskRequest(
            query_type="term",
            term="Spring",
            user_query="How does Spring implement data persistence?",
            run_id=5,
            llm_enabled=False,
        )
    )

    def fake_run_term_flow(*, req: AskRequest, session: DummySession) -> TermFlowResult:
        _ = (req, session)
        return TermFlowResult(
            cluster_payload={"schema_version": "cluster.v1"},
            evidence={"sections": [], "bullets": []},
            retrieval_warnings={"state": "broad_blocked"},
            runtime_state=RUNTIME_STATE_NEEDS_NARROWER_TERM,
            response_guidance=None,
            answer_markdown=None,
            llm_error=None,
        )

    monkeypatch.setattr(runtime, "run_term_flow", fake_run_term_flow)

    result = runtime.run_runtime(request=runtime_request, session=DummySession())

    assert result.status == "blocked"
    assert result.runtime_state == RUNTIME_STATE_NEEDS_NARROWER_TERM
    assert result.final_state["retrieval_warnings"] == {"state": "broad_blocked"}
