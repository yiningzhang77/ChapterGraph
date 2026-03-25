import os
import json
import socket
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

from feature_achievement.llm.prompts import SYSTEM_PROMPT, build_prompt

CONFIG_PATH = Path("config/llm.env")


def _load_local_env_config() -> None:
    if not CONFIG_PATH.exists():
        return

    for raw_line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _normalized_provider() -> str:
    raw = os.getenv("QWEN_PROVIDER", "stub").strip().lower()
    if raw == "openai-compatible":
        return "openai_compatible"
    return raw


def _extract_seed_citations(cluster: dict[str, object]) -> list[str]:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return []
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return []
    return [entry for entry in seed_ids if isinstance(entry, str)]


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required config: {name}")
    return value


def _provider_model(request_model: str) -> str:
    configured_model = os.getenv("QWEN_MODEL", "").strip()
    if configured_model:
        return configured_model
    if request_model.strip():
        return request_model.strip()
    raise RuntimeError("Missing required config: QWEN_MODEL")


def _provider_temperature() -> float:
    raw = os.getenv("QWEN_TEMPERATURE", "0").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError("Invalid QWEN_TEMPERATURE") from exc
    return value


def _provider_max_tokens() -> int | None:
    raw = os.getenv("QWEN_MAX_TOKENS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("Invalid QWEN_MAX_TOKENS") from exc
    if value <= 0:
        raise RuntimeError("Invalid QWEN_MAX_TOKENS")
    return value


def _chat_completions_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def _extract_message_content(payload: dict[str, object]) -> str:
    choices_obj = payload.get("choices")
    choices = choices_obj if isinstance(choices_obj, list) else []
    if not choices:
        raise RuntimeError("LLM response missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("LLM response choice is not an object")
    message_obj = first_choice.get("message")
    message = message_obj if isinstance(message_obj, dict) else None
    if message is None:
        raise RuntimeError("LLM response missing message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text_value = item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                text_parts.append(text_value.strip())
        joined = "\n".join(text_parts).strip()
        if joined:
            return joined
    raise RuntimeError("LLM response missing text content")


def _ask_openai_compatible(
    *,
    query: str,
    query_type: str,
    cluster: dict[str, object],
    retrieval_term: str | None,
    response_guidance: str | None,
    model: str,
    timeout_ms: int,
) -> str:
    base_url = _get_required_env("QWEN_BASE_URL")
    api_key = _get_required_env("QWEN_API_KEY")
    payload: dict[str, object] = {
        "model": _provider_model(model),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_prompt(
                    query,
                    query_type,
                    cluster,
                    retrieval_term=retrieval_term,
                    response_guidance=response_guidance,
                ),
            },
        ],
        "temperature": _provider_temperature(),
    }
    max_tokens = _provider_max_tokens()
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url=_chat_completions_url(base_url),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    timeout_seconds = max(timeout_ms / 1000.0, 1.0)

    try:
        with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except TimeoutError as exc:
        raise RuntimeError(
            f"LLM provider request timed out after {timeout_seconds:.1f}s"
        ) from exc
    except socket.timeout as exc:
        raise RuntimeError(
            f"LLM provider request timed out after {timeout_seconds:.1f}s"
        ) from exc
    except urllib_error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace").strip()
        detail = error_body or exc.reason or "HTTP error"
        raise RuntimeError(
            f"LLM provider request failed ({exc.code}): {detail}"
        ) from exc
    except urllib_error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError(
                f"LLM provider request timed out after {timeout_seconds:.1f}s"
            ) from exc
        if isinstance(exc.reason, socket.timeout):
            raise RuntimeError(
                f"LLM provider request timed out after {timeout_seconds:.1f}s"
            ) from exc
        reason = str(exc.reason) if exc.reason else "network error"
        raise RuntimeError(f"LLM provider request failed: {reason}") from exc

    try:
        response_json = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM provider returned invalid JSON") from exc
    if not isinstance(response_json, dict):
        raise RuntimeError("LLM provider returned non-object JSON")
    return _extract_message_content(response_json)


def ask_qwen(
    query: str,
    query_type: str,
    cluster: dict[str, object],
    retrieval_term: str | None,
    response_guidance: str | None,
    model: str,
    timeout_ms: int,
) -> str:
    _load_local_env_config()
    provider = _normalized_provider()
    _ = (
        SYSTEM_PROMPT,
        build_prompt(
            query,
            query_type,
            cluster,
            retrieval_term=retrieval_term,
            response_guidance=response_guidance,
        ),
        model,
        timeout_ms,
    )

    if provider == "stub":
        citations = _extract_seed_citations(cluster)
        if citations:
            return (
                "## Findings\n"
                "- Stub response: LLM provider is not configured.\n\n"
                "## Citations\n"
                + ", ".join(citations)
            )
        return (
            "## Findings\n"
            "- Stub response: LLM provider is not configured.\n\n"
            "## Citations\nnone"
        )

    if provider in {"openai_compatible", "dashscope"}:
        return _ask_openai_compatible(
            query=query,
            query_type=query_type,
            cluster=cluster,
            retrieval_term=retrieval_term,
            response_guidance=response_guidance,
            model=model,
            timeout_ms=timeout_ms,
        )

    raise RuntimeError(f"Unsupported QWEN_PROVIDER: {provider}")
