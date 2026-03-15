import json
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.db.engine import engine
from feature_achievement.db.models import Run

KNOWN_TERMS = ["Actuator", "Spring", "Security", "Data"]
TARGET_VERSION = "v2_indexed_sections_bullets"
OUTPUT_PATH = Path("tmp/ask_smoke_cluster.json")


def _find_run_id(session: Session) -> int:
    stmt = select(Run).order_by(Run.created_at.desc())
    runs = session.exec(stmt).all()
    for run in runs:
        if run.enrichment_version == TARGET_VERSION and run.id is not None:
            return run.id
    raise RuntimeError(
        f"No run found with enrichment_version={TARGET_VERSION}. "
        "Create runs via /compute-edges first."
    )


def _validate_cluster(cluster: dict[str, object]) -> tuple[int, int, int, int, int, int]:
    required_keys = {
        "schema_version",
        "query",
        "query_type",
        "run_id",
        "enrichment_version",
        "seed",
        "chapters",
        "edges",
        "evidence",
        "constraints",
    }
    missing = [key for key in required_keys if key not in cluster]
    if missing:
        raise RuntimeError(f"Cluster malformed: missing keys={missing}")

    seed = cluster.get("seed")
    if not isinstance(seed, dict):
        raise RuntimeError("Cluster malformed: seed is not an object")

    seed_ids = seed.get("seed_chapter_ids")
    if not isinstance(seed_ids, list):
        raise RuntimeError("Cluster malformed: seed.seed_chapter_ids is not a list")

    chapters = cluster.get("chapters")
    if not isinstance(chapters, list):
        raise RuntimeError("Cluster malformed: chapters is not a list")

    edges = cluster.get("edges")
    if not isinstance(edges, list):
        raise RuntimeError("Cluster malformed: edges is not a list")
    evidence = cluster.get("evidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("Cluster malformed: evidence is not an object")
    evidence_sections = evidence.get("sections")
    evidence_bullets = evidence.get("bullets")
    if not isinstance(evidence_sections, list):
        raise RuntimeError("Cluster malformed: evidence.sections is not a list")
    if not isinstance(evidence_bullets, list):
        raise RuntimeError("Cluster malformed: evidence.bullets is not a list")
    non_null_source_ref_count = 0
    for bullet in evidence_bullets:
        if not isinstance(bullet, dict):
            raise RuntimeError("Cluster malformed: evidence bullet entry is not an object")
        if "source_refs" not in bullet:
            raise RuntimeError("Cluster malformed: evidence bullet missing source_refs key")
        source_refs = bullet.get("source_refs")
        if isinstance(source_refs, list) and len(source_refs) > 0:
            non_null_source_ref_count += 1

    seed_count = len(seed_ids)
    chapter_count = len(chapters)
    edge_count = len(edges)
    evidence_section_count = len(evidence_sections)
    evidence_bullet_count = len(evidence_bullets)

    if seed_count == 0:
        raise RuntimeError("Cluster invalid: empty seed list")
    if chapter_count == 0:
        raise RuntimeError("Cluster invalid: empty chapter list")
    if evidence_bullet_count == 0:
        raise RuntimeError("Cluster invalid: evidence.bullets is empty")
    if non_null_source_ref_count == 0:
        raise RuntimeError(
            "Cluster invalid: evidence.bullets contain no non-null source_refs"
        )
    return (
        seed_count,
        chapter_count,
        edge_count,
        evidence_section_count,
        evidence_bullet_count,
        non_null_source_ref_count,
    )


def _print_cluster_summary(cluster: dict[str, object]) -> None:
    query = cluster.get("query")
    query_type = cluster.get("query_type")
    seed = cluster.get("seed")
    chapters = cluster.get("chapters")
    edges = cluster.get("edges")
    evidence = cluster.get("evidence")
    constraints = cluster.get("constraints")

    print("cluster_summary:")
    print(f"  query: {query}")
    print(f"  query_type: {query_type}")
    print(f"  seed: {seed}")

    print("  chapters:")
    if isinstance(chapters, list):
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            chapter_id = chapter.get("chapter_id")
            title = chapter.get("title")
            book_id = chapter.get("book_id")
            print(
                f"    - chapter_id={chapter_id}, title={title}, book_id={book_id}"
            )
    else:
        print("    - invalid chapters payload")

    print(f"  edges: {edges}")
    print(f"  evidence: {evidence}")
    print(f"  constraints: {constraints}")


def _write_cluster_file(cluster: dict[str, object]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(cluster, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"cluster_json_written={OUTPUT_PATH}")


def main() -> int:
    with Session(engine) as session:
        run_id = _find_run_id(session)
        print(f"using run_id={run_id}")

        last_error: str | None = None
        for term in KNOWN_TERMS:
            req = AskRequest(
                query_type="term",
                term=term,
                user_query=f"Tell me about {term}.",
                run_id=run_id,
                enrichment_version=TARGET_VERSION,
                max_hops=2,
            )
            try:
                cluster = build_cluster(session=session, req=req)
                (
                    seed_count,
                    chapter_count,
                    edge_count,
                    evidence_section_count,
                    evidence_bullet_count,
                    non_null_source_ref_count,
                ) = _validate_cluster(cluster)
                print(f"term={term}")
                print(f"seed_count={seed_count}")
                print(f"chapter_count={chapter_count}")
                print(f"edge_count={edge_count}")
                print(f"evidence_section_count={evidence_section_count}")
                print(f"evidence_bullet_count={evidence_bullet_count}")
                print(f"evidence_non_null_source_ref_count={non_null_source_ref_count}")
                _print_cluster_summary(cluster)
                _write_cluster_file(cluster)
                print("smoke passed")
                return 0
            except HTTPException as exc:
                last_error = f"HTTPException {exc.status_code}: {exc.detail}"
            except RuntimeError as exc:
                last_error = str(exc)

    raise SystemExit(
        "Smoke failed for all known terms. "
        + (last_error or "No error detail available.")
    )


if __name__ == "__main__":
    raise SystemExit(main())
