from pathlib import Path

import pytest

from feature_achievement.llm import qwen_client
from feature_achievement.llm.prompts import SYSTEM_PROMPT, build_prompt
from feature_achievement.llm.qwen_client import ask_qwen


def _cluster(seed_ids: list[str]) -> dict[str, object]:
    return {
        "schema_version": "cluster.v1",
        "query": "Actuator",
        "query_type": "term",
        "run_id": 1,
        "enrichment_version": "v1_bullets+sections",
        "seed": {
            "seed_chapter_ids": seed_ids,
            "seed_reason": "term_ilike",
        },
        "chapters": [],
        "edges": [],
        "constraints": {},
    }


def test_system_prompt_mentions_cluster_grounding() -> None:
    assert "Only use facts from the provided cluster JSON." in SYSTEM_PROMPT
    assert "cite chapter_id" in SYSTEM_PROMPT


def test_build_prompt_includes_query_type_and_cluster_json() -> None:
    prompt = build_prompt(
        query="What is actuator?",
        query_type="term",
        cluster=_cluster(["spring::ch1"]),
    )

    assert "User question: What is actuator?" in prompt
    assert "Query type: term" in prompt
    assert '"seed_chapter_ids": ["spring::ch1"]' in prompt
    assert "Cluster JSON:" in prompt


def test_ask_qwen_stub_returns_seed_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "stub")

    answer = ask_qwen(
        query="Actuator",
        query_type="term",
        cluster=_cluster(["spring::ch1", "spring::ch2"]),
        model="qwen",
        timeout_ms=5000,
    )

    assert "Stub response" in answer
    assert "spring::ch1, spring::ch2" in answer


def test_ask_qwen_raises_for_unsupported_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "unsupported")

    with pytest.raises(RuntimeError) as exc:
        ask_qwen(
            query="Actuator",
            query_type="term",
            cluster=_cluster(["spring::ch1"]),
            model="qwen",
            timeout_ms=5000,
        )

    assert "Unsupported QWEN_PROVIDER" in str(exc.value)
