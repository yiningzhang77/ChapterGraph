import os
from pathlib import Path

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


def _extract_seed_citations(cluster: dict[str, object]) -> list[str]:
    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        return []
    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        return []
    return [entry for entry in seed_ids if isinstance(entry, str)]


def ask_qwen(
    query: str,
    query_type: str,
    cluster: dict[str, object],
    model: str,
    timeout_ms: int,
) -> str:
    _load_local_env_config()
    provider = os.getenv("QWEN_PROVIDER", "stub").strip().lower()
    _ = (SYSTEM_PROMPT, build_prompt(query, query_type, cluster), model, timeout_ms)

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

    raise RuntimeError(f"Unsupported QWEN_PROVIDER: {provider}")
