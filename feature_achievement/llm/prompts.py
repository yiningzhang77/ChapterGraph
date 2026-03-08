import json


SYSTEM_PROMPT = (
    "You are a grounded assistant. "
    "Only use facts from the provided cluster JSON. "
    "No external knowledge. "
    "Every key statement must cite chapter_id."
)


def build_prompt(
    query: str,
    query_type: str,
    cluster: dict[str, object],
) -> str:
    return (
        f"User question: {query}\n"
        f"Query type: {query_type}\n\n"
        "Tasks:\n"
        "1) Give concise answer.\n"
        "2) Explain based on cluster edges and chapter_text.\n"
        "3) Add a 'Citations' section listing chapter_id values.\n\n"
        f"Cluster JSON:\n{json.dumps(cluster, ensure_ascii=False)}"
    )

