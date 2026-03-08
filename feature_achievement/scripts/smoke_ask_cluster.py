import json
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from feature_achievement.api.schemas.ask import AskRequest
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.db.engine import engine
from feature_achievement.db.models import Run

KNOWN_TERMS = ["Actuator", "Spring", "Security", "Data"]
TARGET_VERSION = "v1_bullets+sections"
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


def _validate_cluster(cluster: dict[str, object]) -> tuple[int, int, int]:
    required_keys = {
        "schema_version",
        "query",
        "query_type",
        "run_id",
        "enrichment_version",
        "seed",
        "chapters",
        "edges",
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

    seed_count = len(seed_ids)
    chapter_count = len(chapters)
    edge_count = len(edges)

    if seed_count == 0:
        raise RuntimeError("Cluster invalid: empty seed list")
    if chapter_count == 0:
        raise RuntimeError("Cluster invalid: empty chapter list")
    return seed_count, chapter_count, edge_count


def _print_cluster_summary(cluster: dict[str, object]) -> None:
    query = cluster.get("query")
    query_type = cluster.get("query_type")
    seed = cluster.get("seed")
    chapters = cluster.get("chapters")
    edges = cluster.get("edges")
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
                query=term,
                query_type="term",
                run_id=run_id,
                enrichment_version=TARGET_VERSION,
                max_hops=2,
            )
            try:
                cluster = build_cluster(session=session, req=req)
                seed_count, chapter_count, edge_count = _validate_cluster(cluster)
                print(f"term={term}")
                print(f"seed_count={seed_count}")
                print(f"chapter_count={chapter_count}")
                print(f"edge_count={edge_count}")
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
