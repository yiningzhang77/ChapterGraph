from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.runtime_adapter import to_runtime_request


def test_to_runtime_request_maps_term_request_fields() -> None:
    req = AskRequest(
        query_type="term",
        term="Actuator",
        user_query="Tell me about Actuator",
        run_id=5,
        enrichment_version="v2_indexed_sections_bullets",
        llm_enabled=True,
        llm_model="qwen",
        llm_timeout_ms=20_000,
        return_cluster=True,
        return_graph_fragment=False,
    )

    runtime_req = to_runtime_request(req)

    assert runtime_req.query_type == "term"
    assert runtime_req.term == "Actuator"
    assert runtime_req.user_query == "Tell me about Actuator"
    assert runtime_req.query == "Tell me about Actuator"
    assert runtime_req.chapter_id is None
    assert runtime_req.run_id == 5
    assert runtime_req.max_hops == 2
    assert runtime_req.seed_top_k == 5
    assert runtime_req.neighbor_top_k == 40
    assert runtime_req.section_top_k == 10
    assert runtime_req.bullet_top_k == 20
    assert runtime_req.min_edge_score == 0.2
    assert runtime_req.return_cluster is True
    assert runtime_req.return_graph_fragment is False


def test_to_runtime_request_maps_chapter_request_fields() -> None:
    req = AskRequest(
        query_type="chapter",
        chapter_id="spring::ch2",
        query="Explain selected chapter",
        run_id=7,
        enrichment_version="v2_indexed_sections_bullets",
        llm_enabled=False,
        return_cluster=False,
        return_graph_fragment=True,
    )

    runtime_req = to_runtime_request(req)

    assert runtime_req.query_type == "chapter"
    assert runtime_req.chapter_id == "spring::ch2"
    assert runtime_req.query == "Explain selected chapter"
    assert runtime_req.term is None
    assert runtime_req.user_query is None
    assert runtime_req.run_id == 7
    assert runtime_req.max_hops == 2
    assert runtime_req.seed_top_k == 5
    assert runtime_req.neighbor_top_k == 40
    assert runtime_req.section_top_k == 10
    assert runtime_req.bullet_top_k == 20
    assert runtime_req.min_edge_score == 0.2
    assert runtime_req.return_cluster is False
    assert runtime_req.return_graph_fragment is True
