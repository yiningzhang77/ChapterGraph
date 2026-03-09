from feature_achievement.api.schemas.ask import AskRequest


def test_ask_request_defaults_and_query_trim() -> None:
    req = AskRequest.model_validate(
        {
            "query": "  Actuator  ",
            "run_id": 9,
        }
    )

    assert req.query == "Actuator"
    assert req.query_type == "term"
    assert req.enrichment_version == "v2_indexed_sections_bullets"
    assert req.max_hops == 2
    assert req.section_top_k == 10
    assert req.bullet_top_k == 20
    assert req.llm_enabled is True
    assert req.return_cluster is True
    assert req.return_graph_fragment is True


def test_ask_request_chapter_uses_query_as_chapter_id_when_missing() -> None:
    req = AskRequest.model_validate(
        {
            "query": " spring-in-action::ch3 ",
            "query_type": "chapter",
            "run_id": 3,
        }
    )

    assert req.query == "spring-in-action::ch3"
    assert req.chapter_id == "spring-in-action::ch3"


def test_ask_request_chapter_keeps_explicit_chapter_id() -> None:
    req = AskRequest.model_validate(
        {
            "query": "Explain this chapter",
            "query_type": "chapter",
            "chapter_id": "spring-in-action::ch5",
            "run_id": 5,
        }
    )

    assert req.query == "Explain this chapter"
    assert req.chapter_id == "spring-in-action::ch5"
