import pytest
from pydantic import ValidationError

from feature_achievement.api.schemas.ask import AskRequest


def test_term_request_with_term_only_gets_default_user_query() -> None:
    req = AskRequest.model_validate(
        {
            "query_type": "term",
            "term": "  Actuator  ",
            "run_id": 9,
        }
    )

    assert req.term == "Actuator"
    assert req.user_query == 'Explain the term "Actuator" using the retrieved cluster.'
    assert req.query == req.user_query
    assert req.query_type == "term"
    assert req.enrichment_version == "v2_indexed_sections_bullets"
    assert req.max_hops == 2
    assert req.section_top_k == 10
    assert req.bullet_top_k == 20
    assert req.llm_enabled is True
    assert req.return_cluster is True
    assert req.return_graph_fragment is True


def test_term_request_keeps_explicit_user_query() -> None:
    req = AskRequest.model_validate(
        {
            "query_type": "term",
            "term": " JdbcTemplate ",
            "user_query": "  Explain how JdbcTemplate works.  ",
            "run_id": 9,
        }
    )

    assert req.term == "JdbcTemplate"
    assert req.user_query == "Explain how JdbcTemplate works."
    assert req.query == "Explain how JdbcTemplate works."


def test_term_request_requires_term() -> None:
    with pytest.raises(ValidationError) as exc:
        AskRequest.model_validate(
            {
                "query_type": "term",
                "user_query": "Tell me about Actuator",
                "run_id": 9,
            }
        )

    assert "term is required for term query_type" in str(exc.value)


def test_chapter_request_with_chapter_id_only_gets_default_query() -> None:
    req = AskRequest.model_validate(
        {
            "query_type": "chapter",
            "chapter_id": " spring-in-action::ch3 ",
            "run_id": 3,
        }
    )

    assert req.chapter_id == "spring-in-action::ch3"
    assert (
        req.query
        == 'Summarize the selected chapter "spring-in-action::ch3" using the retrieved cluster.'
    )


def test_chapter_request_keeps_explicit_query() -> None:
    req = AskRequest.model_validate(
        {
            "query_type": "chapter",
            "chapter_id": "spring-in-action::ch5",
            "query": " Explain this chapter ",
            "run_id": 5,
        }
    )

    assert req.query == "Explain this chapter"
    assert req.chapter_id == "spring-in-action::ch5"


def test_chapter_request_requires_chapter_id() -> None:
    with pytest.raises(ValidationError) as exc:
        AskRequest.model_validate(
            {
                "query_type": "chapter",
                "query": "Explain this chapter",
                "run_id": 5,
            }
        )

    assert "chapter_id is required for chapter query_type" in str(exc.value)
