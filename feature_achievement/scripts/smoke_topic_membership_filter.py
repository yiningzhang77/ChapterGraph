from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from sqlmodel import Session, select

from feature_achievement.db.engine import engine
from feature_achievement.db.models import Run
from feature_achievement.topic_study.discovery import build_topic_catalog
from feature_achievement.topic_study.membership_filter import build_refined_topic_catalog


def main() -> None:
    with Session(engine) as session:
        run = session.exec(select(Run).order_by(Run.created_at.desc())).first()
        if run is None or run.id is None:
            raise SystemExit("smoke_topic_membership_filter failed: no run found")

        raw_catalog = build_topic_catalog(
            session=session,
            run_id=run.id,
            enrichment_version=run.enrichment_version,
        )
        refined_catalog = build_refined_topic_catalog(
            session=session,
            topic_catalog=raw_catalog,
        )

    if not refined_catalog.topics:
        raise SystemExit("smoke_topic_membership_filter failed: empty refined catalog")

    malformed_topics = [
        topic.topic_id
        for topic in refined_catalog.topics
        if not topic.label
        or not topic.representative_chapter_id
        or not topic.core_chapter_ids
    ]
    if malformed_topics:
        raise SystemExit(
            "smoke_topic_membership_filter failed: malformed refined topics "
            + ", ".join(malformed_topics)
        )

    broad_count = sum(1 for topic in refined_catalog.topics if topic.broad_topic_flag)
    print(f"run_id={refined_catalog.run_id}")
    print(f"enrichment_version={refined_catalog.enrichment_version}")
    print(f"topic_count={len(refined_catalog.topics)}")
    print(f"broad_topic_count={broad_count}")
    print("sample_topics:")
    for topic in sorted(
        refined_catalog.topics,
        key=lambda item: (
            -len(item.core_chapter_ids),
            -len(item.peripheral_chapter_ids),
            item.topic_id,
        ),
    )[:8]:
        print(f"  - {topic.topic_id} | label={topic.label}")
        print(f"    representative={topic.representative_chapter_id}")
        print(f"    core={topic.core_chapter_ids}")
        print(f"    peripheral={topic.peripheral_chapter_ids}")
        print(f"    excluded={topic.excluded_chapter_ids}")
        print(f"    broad={topic.broad_topic_flag}")

    output_path = Path("tmp/refined_topic_catalog_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(refined_catalog), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"output_written={output_path}")
    print("smoke_topic_membership_filter passed")


if __name__ == "__main__":
    main()
