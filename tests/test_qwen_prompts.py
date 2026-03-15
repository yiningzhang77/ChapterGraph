from pathlib import Path
import io
import json

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
        "enrichment_version": "v2_indexed_sections_bullets",
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


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_ask_qwen_openai_compatible_returns_message_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "openai_compatible")
    monkeypatch.setenv("QWEN_BASE_URL", "https://example.test")
    monkeypatch.setenv("QWEN_API_KEY", "secret")
    monkeypatch.setenv("QWEN_MODEL", "qwen-max")
    monkeypatch.setenv("QWEN_TEMPERATURE", "0")
    monkeypatch.setenv("QWEN_MAX_TOKENS", "256")

    captured: dict[str, object] = {}

    def fake_urlopen(req: object, timeout: float) -> _FakeHttpResponse:
        assert isinstance(timeout, float)
        captured["timeout"] = timeout
        request = req
        full_url = getattr(request, "full_url")
        headers = dict(getattr(request, "headers"))
        data = getattr(request, "data")
        captured["url"] = full_url
        captured["headers"] = headers
        captured["body"] = json.loads(data.decode("utf-8"))
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "## Findings\n- Real answer\n\n## Citations\nspring::ch1"
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(qwen_client.urllib_request, "urlopen", fake_urlopen)

    answer = ask_qwen(
        query="Actuator",
        query_type="term",
        cluster=_cluster(["spring::ch1"]),
        model="qwen",
        timeout_ms=4500,
    )

    assert "Real answer" in answer
    assert captured["url"] == "https://example.test/v1/chat/completions"
    headers = captured["headers"]
    assert headers["Authorization"] == "Bearer secret"
    body = captured["body"]
    assert body["model"] == "qwen-max"
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 256
    assert captured["timeout"] == 4.5


def test_ask_qwen_openai_compatible_supports_text_array_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "openai_compatible")
    monkeypatch.setenv("QWEN_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("QWEN_API_KEY", "secret")
    monkeypatch.setenv("QWEN_MODEL", "qwen-max")

    def fake_urlopen(req: object, timeout: float) -> _FakeHttpResponse:
        _ = (req, timeout)
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "## Findings"},
                                {"type": "text", "text": "- Array answer"},
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(qwen_client.urllib_request, "urlopen", fake_urlopen)

    answer = ask_qwen(
        query="Actuator",
        query_type="term",
        cluster=_cluster(["spring::ch1"]),
        model="qwen",
        timeout_ms=5000,
    )

    assert "Array answer" in answer


def test_ask_qwen_openai_compatible_requires_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "openai_compatible")
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "secret")

    with pytest.raises(RuntimeError) as exc:
        ask_qwen(
            query="Actuator",
            query_type="term",
            cluster=_cluster(["spring::ch1"]),
            model="qwen",
            timeout_ms=5000,
        )

    assert "Missing required config: QWEN_BASE_URL" in str(exc.value)


def test_ask_qwen_openai_compatible_surfaces_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qwen_client, "CONFIG_PATH", Path("config/llm.env.missing"))
    monkeypatch.setenv("QWEN_PROVIDER", "openai_compatible")
    monkeypatch.setenv("QWEN_BASE_URL", "https://example.test")
    monkeypatch.setenv("QWEN_API_KEY", "secret")
    monkeypatch.setenv("QWEN_MODEL", "qwen-max")

    def fake_urlopen(req: object, timeout: float) -> _FakeHttpResponse:
        _ = (req, timeout)
        raise qwen_client.urllib_error.HTTPError(
            url="https://example.test/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr(qwen_client.urllib_request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc:
        ask_qwen(
            query="Actuator",
            query_type="term",
            cluster=_cluster(["spring::ch1"]),
            model="qwen",
            timeout_ms=5000,
        )

    assert "LLM provider request failed (401)" in str(exc.value)
