import json


SYSTEM_PROMPT = (
    "You are a grounded assistant. "
    "Only use facts from the provided cluster JSON. "
    "No external knowledge. "
    "Every key statement must cite chapter_id. "
    "Follow the user's language. "
    "If the user asks in Chinese, answer in Chinese. "
    "For technical terms, either keep the original English term or write Chinese followed by English in parentheses. "
    "Never create mixed-script partial translations such as a half-Chinese half-English term. "
    "Prefer concrete section and bullet evidence over vague chapter summary. "
    "If the evidence is thin, say that directly instead of guessing."
)


def _query_type_tasks(query_type: str) -> str:
    if query_type == "chapter":
        return (
            "Tasks:\n"
            "1) Summarize the selected chapter in a structured way.\n"
            "2) Prioritize the selected chapter's major sections and important bullets.\n"
            "3) Use neighbor chapters only as secondary context.\n"
            "4) Add a 'Citations' section listing chapter_id values.\n\n"
        )
    return (
        "Tasks:\n"
        "1) Give concise answer.\n"
        "2) Explain based on cluster edges and chapter_text.\n"
        "3) Connect related chapters when the cluster supports it.\n"
        "4) Add a 'Citations' section listing chapter_id values.\n\n"
    )


def build_prompt(
    query: str,
    query_type: str,
    cluster: dict[str, object],
    retrieval_term: str | None = None,
) -> str:
    return (
        f"User question: {query}\n"
        f"Query type: {query_type}\n"
        + (f"Retrieval term: {retrieval_term}\n\n" if retrieval_term else "\n")
        + _query_type_tasks(query_type)
        + f"Cluster JSON:\n{json.dumps(cluster, ensure_ascii=False)}"
    )
