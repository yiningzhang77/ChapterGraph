from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from sqlmodel import Session, select

from feature_achievement.db.engine import engine
from feature_achievement.db.models import Run
from feature_achievement.topic_study.discovery import build_topic_catalog


def main() -> None:
    with Session(engine) as session:
        run = session.exec(select(Run).order_by(Run.created_at.desc())).first()
        if run is None or run.id is None:
            raise SystemExit("smoke_topic_discovery failed: no run found")

        catalog = build_topic_catalog(
            session=session,
            run_id=run.id,
            enrichment_version=run.enrichment_version,
        )

    if not catalog.topics:
        raise SystemExit("smoke_topic_discovery failed: empty topic catalog")

    malformed_topics = [
        topic.topic_id
        for topic in catalog.topics
        if not topic.label or not topic.chapter_ids or not topic.seed_chapter_id
    ]
    if malformed_topics:
        raise SystemExit(
            "smoke_topic_discovery failed: malformed topics "
            + ", ".join(malformed_topics)
        )

    singleton_count = sum(1 for topic in catalog.topics if topic.cluster_type == "singleton")
    component_count = len(catalog.topics) - singleton_count

    print(f"run_id={catalog.run_id}")
    print(f"enrichment_version={catalog.enrichment_version}")
    print(f"topic_count={len(catalog.topics)}")
    print(f"singleton_count={singleton_count}")
    print(f"component_count={component_count}")
    print("sample_topics:")
    for topic in catalog.topics[:8]:
        print(
            f"  - {topic.topic_id} | {topic.cluster_type} | "
            f"chapters={len(topic.chapter_ids)} | label={topic.label}"
        )
        print(f"    seed={topic.seed_chapter_id}")
        print(f"    books={topic.book_ids}")
        print(f"    chapters={topic.chapter_ids}")

    output_path = Path("tmp/topic_catalog_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(catalog), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"output_written={output_path}")
    print("smoke_topic_discovery passed")


if __name__ == "__main__":
    main()
