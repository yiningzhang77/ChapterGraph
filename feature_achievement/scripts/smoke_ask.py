import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from feature_achievement.api.main import app

KNOWN_TERMS = ["Actuator", "Spring", "Security", "Data"]
TARGET_VERSION = "v1_bullets+sections"
OUTPUT_PATH = Path("tmp/ask_smoke_response.json")


def _pick_run_id(client: TestClient) -> int:
    response = client.get("/runs")
    response.raise_for_status()
    runs = response.json()
    if not isinstance(runs, list) or not runs:
        raise RuntimeError("No runs found. Create one via POST /compute-edges first.")

    for run in runs:
        run_id = run.get("id")
        if isinstance(run_id, int):
            return run_id
    raise RuntimeError("No valid run id found in /runs response.")


def _post_ask(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/ask", json=payload)
    if response.status_code != 200:
        detail = response.text
        try:
            body = response.json()
            detail = body.get("detail", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"/ask failed ({response.status_code}): {detail}")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("/ask returned non-object response.")
    return body


def _validate_cluster(response_body: dict[str, object]) -> dict[str, object]:
    cluster = response_body.get("cluster")
    if not isinstance(cluster, dict):
        raise RuntimeError("Missing cluster in /ask response.")

    seed = cluster.get("seed")
    chapters = cluster.get("chapters")
    edges = cluster.get("edges")
    if not isinstance(seed, dict):
        raise RuntimeError("Malformed cluster: seed must be an object.")
    if not isinstance(chapters, list):
        raise RuntimeError("Malformed cluster: chapters must be a list.")
    if not isinstance(edges, list):
        raise RuntimeError("Malformed cluster: edges must be a list.")
    if len(chapters) == 0:
        raise RuntimeError("Cluster has no chapters.")

    return cluster


def _write_output(data: dict[str, object]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"output_written={OUTPUT_PATH}")


def main() -> int:
    os.environ["QWEN_PROVIDER"] = "stub"

    with TestClient(app) as client:
        run_id = _pick_run_id(client)
        print(f"run_id={run_id}")

        term_response: dict[str, object] | None = None
        last_error: str | None = None
        for term in KNOWN_TERMS:
            try:
                candidate = _post_ask(
                    client,
                    {
                        "query": term,
                        "query_type": "term",
                        "run_id": run_id,
                        "enrichment_version": TARGET_VERSION,
                        "max_hops": 2,
                        "llm_enabled": True,
                        "return_cluster": True,
                        "return_graph_fragment": True,
                    },
                )
                _validate_cluster(candidate)
                term_response = candidate
                print(f"term_query={term}")
                break
            except RuntimeError as exc:
                last_error = str(exc)

        if term_response is None:
            raise SystemExit(
                "Term-mode smoke failed for all known terms. "
                + (last_error or "No error details.")
            )

        term_cluster = _validate_cluster(term_response)
        term_seed = term_cluster.get("seed")
        seed_ids = term_seed.get("seed_chapter_ids") if isinstance(term_seed, dict) else None
        if not isinstance(seed_ids, list) or not seed_ids:
            raise SystemExit("Term cluster missing seed_chapter_ids.")

        first_seed = seed_ids[0]
        if not isinstance(first_seed, str):
            raise SystemExit("Seed chapter id is not a string.")

        chapter_response = _post_ask(
            client,
            {
                "query": "Explain the selected chapter.",
                "query_type": "chapter",
                "chapter_id": first_seed,
                "run_id": run_id,
                "enrichment_version": TARGET_VERSION,
                "max_hops": 2,
                "llm_enabled": True,
                "return_cluster": True,
                "return_graph_fragment": True,
            },
        )
        chapter_cluster = _validate_cluster(chapter_response)

        term_chapter_count = len(term_cluster.get("chapters", []))
        term_edge_count = len(term_cluster.get("edges", []))
        chapter_chapter_count = len(chapter_cluster.get("chapters", []))
        chapter_edge_count = len(chapter_cluster.get("edges", []))

        print(f"term_cluster chapters={term_chapter_count} edges={term_edge_count}")
        print(f"chapter_cluster chapters={chapter_chapter_count} edges={chapter_edge_count}")

        term_answer = term_response.get("answer_markdown")
        chapter_answer = chapter_response.get("answer_markdown")
        print(f"term_answer_preview={str(term_answer)[:120]}")
        print(f"chapter_answer_preview={str(chapter_answer)[:120]}")

        _write_output(
            {
                "run_id": run_id,
                "term_response": term_response,
                "chapter_response": chapter_response,
            }
        )
        print("smoke_ask passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
