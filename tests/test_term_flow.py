from typing import cast

from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask import term_flow


def test_run_term_flow_returns_service_shape(monkeypatch) -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        llm_enabled=False,
    )

    monkeypatch.setattr(
        term_flow,
        "_build_term_cluster",
        lambda **kwargs: {"cluster_payload": {"chapters": []}, "evidence": {"bullets": []}},
    )
    monkeypatch.setattr(
        term_flow,
        "_evaluate_term_quality",
        lambda **kwargs: {"retrieval_warnings": {"state": "normal"}},
    )
    monkeypatch.setattr(
        term_flow,
        "_build_narrowing_payload",
        lambda **kwargs: {"suggested_terms": ["Actuator"], "suggested_term_diagnostics": None},
    )
    monkeypatch.setattr(
        term_flow,
        "_generate_term_answer",
        lambda **kwargs: {
            "response_state": "normal",
            "response_guidance": None,
            "answer_markdown": "answer",
            "llm_error": None,
        },
    )

    result = term_flow.run_term_flow(
        req=req,
        session=cast(Session, object()),
    )

    assert result == {
        "cluster_payload": {"chapters": []},
        "evidence": {"bullets": []},
        "retrieval_warnings": {"state": "normal"},
        "narrowing_payload": {
            "suggested_terms": ["Actuator"],
            "suggested_term_diagnostics": None,
        },
        "response_state": "normal",
        "response_guidance": None,
        "answer_markdown": "answer",
        "llm_error": None,
    }
