import os

from feature_achievement.llm.prompts import SYSTEM_PROMPT, build_prompt


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

