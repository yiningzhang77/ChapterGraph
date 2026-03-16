import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from feature_achievement.api.main import app

KNOWN_TERMS = ["Actuator", "Spring", "Security", "Data"]
TARGET_VERSION = "v2_indexed_sections_bullets"
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
    evidence = response_body.get("evidence")
    if evidence is None:
        evidence = cluster.get("evidence")
    if not isinstance(seed, dict):
        raise RuntimeError("Malformed cluster: seed must be an object.")
    if not isinstance(chapters, list):
        raise RuntimeError("Malformed cluster: chapters must be a list.")
    if not isinstance(edges, list):
        raise RuntimeError("Malformed cluster: edges must be a list.")
    if not isinstance(evidence, dict):
        raise RuntimeError("Malformed cluster: evidence must be an object.")
    evidence_sections = evidence.get("sections")
    evidence_bullets = evidence.get("bullets")
    if not isinstance(evidence_sections, list):
        raise RuntimeError("Malformed cluster: evidence.sections must be a list.")
    if not isinstance(evidence_bullets, list):
        raise RuntimeError("Malformed cluster: evidence.bullets must be a list.")
    for bullet in evidence_bullets:
        if not isinstance(bullet, dict):
            raise RuntimeError(
                "Malformed cluster: evidence bullet entry must be an object."
            )
        if "source_refs" not in bullet:
            raise RuntimeError(
                "Malformed cluster: evidence bullet missing source_refs key."
            )
    if len(chapters) == 0:
        raise RuntimeError("Cluster has no chapters.")

    return cluster


def _write_output(data: dict[str, object]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
                        "query_type": "term",
                        "term": term,
                        "user_query": f"Tell me about {term}.",
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
        seed_ids = (
            term_seed.get("seed_chapter_ids") if isinstance(term_seed, dict) else None
        )
        if not isinstance(seed_ids, list) or not seed_ids:
            raise SystemExit("Term cluster missing seed_chapter_ids.")

        first_seed = seed_ids[0]
        if not isinstance(first_seed, str):
            raise SystemExit("Seed chapter id is not a string.")

        chapter_response = _post_ask(
            client,
            {
                "query_type": "chapter",
                "chapter_id": first_seed,
                "query": "",
                "run_id": run_id,
                "enrichment_version": TARGET_VERSION,
                "max_hops": 2,
                "llm_enabled": True,
                "return_cluster": True,
                "return_graph_fragment": True,
            },
        )
        chapter_cluster = _validate_cluster(chapter_response)

        broad_overview_response = _post_ask(
            client,
            {
                "query_type": "term",
                "term": "Spring",
                "user_query": "What is Spring?",
                "run_id": run_id,
                "enrichment_version": TARGET_VERSION,
                "max_hops": 2,
                "llm_enabled": True,
                "return_cluster": True,
                "return_graph_fragment": True,
            },
        )
        _validate_cluster(broad_overview_response)
        broad_overview_meta = broad_overview_response.get("meta")
        if not isinstance(broad_overview_meta, dict):
            raise SystemExit("Broad-overview term response missing meta.")
        if broad_overview_meta.get("response_state") != "broad_overview":
            raise SystemExit("Expected broad_overview state for overview query.")

        broad_blocked_response = _post_ask(
            client,
            {
                "query_type": "term",
                "term": "Spring",
                "user_query": "How does Spring implement data persistence?",
                "run_id": run_id,
                "enrichment_version": TARGET_VERSION,
                "max_hops": 2,
                "llm_enabled": True,
                "return_cluster": True,
                "return_graph_fragment": True,
            },
        )
        _validate_cluster(broad_blocked_response)
        broad_blocked_meta = broad_blocked_response.get("meta")
        if not isinstance(broad_blocked_meta, dict):
            raise SystemExit("Broad-blocked term response missing meta.")
        if broad_blocked_meta.get("response_state") != "needs_narrower_term":
            raise SystemExit("Expected needs_narrower_term state for precise broad query.")
        if broad_blocked_response.get("answer_markdown") is not None:
            raise SystemExit("Blocked broad query should not include answer_markdown.")
        broad_blocked_warnings = broad_blocked_meta.get("retrieval_warnings")
        if not isinstance(broad_blocked_warnings, dict):
            raise SystemExit("Broad-blocked response missing retrieval_warnings.")
        suggested_terms = broad_blocked_warnings.get("suggested_terms")
        if not isinstance(suggested_terms, list) or not suggested_terms:
            raise SystemExit("Broad-blocked response missing suggested_terms.")
        suggested_term_diagnostics = broad_blocked_warnings.get("suggested_term_diagnostics")
        if not isinstance(suggested_term_diagnostics, list):
            raise SystemExit(
                "Broad-blocked response missing suggested_term_diagnostics."
            )
        if (
            "data persistence" in suggested_terms
            and "Spring Data" in suggested_terms
            and suggested_terms.index("data persistence") > suggested_terms.index("Spring Data")
        ):
            raise SystemExit(
                "Expected data persistence to rank above Spring Data in reranked suggestions."
            )
        if (
            "JdbcTemplate" in suggested_terms
            and "Spring Data" in suggested_terms
            and suggested_terms.index("JdbcTemplate") > suggested_terms.index("Spring Data")
        ):
            raise SystemExit(
                "Expected JdbcTemplate to rank above Spring Data in reranked suggestions."
            )

        narrowed_response: dict[str, object] | None = None
        narrowed_term: str | None = None
        for suggested_term in suggested_terms:
            if not isinstance(suggested_term, str):
                continue
            candidate = _post_ask(
                client,
                {
                    "query_type": "term",
                    "term": suggested_term,
                    "user_query": "How does Spring implement data persistence?",
                    "run_id": run_id,
                    "enrichment_version": TARGET_VERSION,
                    "max_hops": 2,
                    "llm_enabled": True,
                    "return_cluster": True,
                    "return_graph_fragment": True,
                },
            )
            _validate_cluster(candidate)
            candidate_meta = candidate.get("meta")
            if not isinstance(candidate_meta, dict):
                continue
            if candidate_meta.get("response_state") != "needs_narrower_term":
                narrowed_response = candidate
                narrowed_term = suggested_term
                break

        if narrowed_response is None or narrowed_term is None:
            raise SystemExit(
                "No suggested term cleared the blocked broad-term state."
            )

        term_chapter_count = len(term_cluster.get("chapters", []))
        term_edge_count = len(term_cluster.get("edges", []))
        term_evidence = term_response.get("evidence")
        if term_evidence is None:
            term_evidence = term_cluster.get("evidence")
        term_section_count = 0
        term_bullet_count = 0
        if isinstance(term_evidence, dict):
            sections = term_evidence.get("sections")
            bullets = term_evidence.get("bullets")
            term_section_count = len(sections) if isinstance(sections, list) else 0
            term_bullet_count = len(bullets) if isinstance(bullets, list) else 0
        chapter_chapter_count = len(chapter_cluster.get("chapters", []))
        chapter_edge_count = len(chapter_cluster.get("edges", []))
        chapter_evidence = chapter_response.get("evidence")
        if chapter_evidence is None:
            chapter_evidence = chapter_cluster.get("evidence")
        chapter_section_count = 0
        chapter_bullet_count = 0
        if isinstance(chapter_evidence, dict):
            sections = chapter_evidence.get("sections")
            bullets = chapter_evidence.get("bullets")
            chapter_section_count = len(sections) if isinstance(sections, list) else 0
            chapter_bullet_count = len(bullets) if isinstance(bullets, list) else 0

        print(f"term_cluster chapters={term_chapter_count} edges={term_edge_count}")
        print(
            f"term_cluster evidence_sections={term_section_count} evidence_bullets={term_bullet_count}"
        )
        print(
            f"chapter_cluster chapters={chapter_chapter_count} edges={chapter_edge_count}"
        )
        print(
            f"chapter_cluster evidence_sections={chapter_section_count} evidence_bullets={chapter_bullet_count}"
        )

        term_answer = term_response.get("answer_markdown")
        chapter_answer = chapter_response.get("answer_markdown")
        broad_overview_answer = broad_overview_response.get("answer_markdown")
        broad_blocked_answer = broad_blocked_response.get("answer_markdown")
        narrowed_meta = narrowed_response.get("meta")
        narrowed_state = (
            narrowed_meta.get("response_state")
            if isinstance(narrowed_meta, dict)
            else None
        )
        narrowed_answer = narrowed_response.get("answer_markdown")
        print(f"term_answer_preview={str(term_answer)[:120]}")
        print(f"chapter_answer_preview={str(chapter_answer)[:120]}")
        print(
            "broad_overview_state="
            + str(broad_overview_meta.get("response_state"))
        )
        print(
            "broad_blocked_state="
            + str(broad_blocked_meta.get("response_state"))
        )
        print(f"broad_overview_answer_preview={str(broad_overview_answer)[:120]}")
        print(f"broad_blocked_answer_preview={str(broad_blocked_answer)[:120]}")
        print(f"broad_blocked_suggested_terms={suggested_terms}")
        print(f"narrowed_term={narrowed_term}")
        print(f"narrowed_state={str(narrowed_state)}")
        print(f"narrowed_answer_preview={str(narrowed_answer)[:120]}")

        _write_output(
            {
                "run_id": run_id,
                "term_response": term_response,
                "chapter_response": chapter_response,
                "broad_overview_response": broad_overview_response,
                "broad_blocked_response": broad_blocked_response,
                "narrowed_term": narrowed_term,
                "narrowed_response": narrowed_response,
            }
        )
        print("smoke_ask passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
