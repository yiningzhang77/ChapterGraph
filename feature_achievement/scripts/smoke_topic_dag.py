from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from sqlmodel import Session, select

from feature_achievement.db.engine import engine
from feature_achievement.db.models import Run
from feature_achievement.topic_study.dag_builder import build_topic_dag
from feature_achievement.topic_study.discovery import build_topic_catalog
from feature_achievement.topic_study.membership_filter import build_refined_topic_catalog


def main() -> None:
    with Session(engine) as session:
        run = session.exec(select(Run).order_by(Run.created_at.desc())).first()
        if run is None or run.id is None:
            raise SystemExit("smoke_topic_dag failed: no run found")

        raw_catalog = build_topic_catalog(
            session=session,
            run_id=run.id,
            enrichment_version=run.enrichment_version,
        )
        refined_catalog = build_refined_topic_catalog(
            session=session,
            topic_catalog=raw_catalog,
        )
        dag = build_topic_dag(catalog=refined_catalog)

    if not dag.topics:
        raise SystemExit("smoke_topic_dag failed: empty topic dag")

    malformed_relations = [
        relation
        for relation in dag.relations
        if relation.from_topic_id == relation.to_topic_id or not relation.reason
    ]
    if malformed_relations:
        raise SystemExit("smoke_topic_dag failed: malformed relation output")

    broad_topic_ids = {
        topic.topic_id
        for topic in dag.topics
        if topic.broad_topic_flag
    }
    broad_structural_relations = [
        relation
        for relation in dag.relations
        if relation.relation_type == "prerequisite"
        and (
            relation.from_topic_id in broad_topic_ids
            or relation.to_topic_id in broad_topic_ids
        )
    ]

    print(f"run_id={dag.run_id}")
    print(f"enrichment_version={dag.enrichment_version}")
    print(f"topic_count={len(dag.topics)}")
    print(f"relation_count={len(dag.relations)}")
    print(f"entry_topic_ids={dag.entry_topic_ids}")
    print(f"broad_topic_ids={sorted(broad_topic_ids)}")
    print(f"broad_structural_relation_count={len(broad_structural_relations)}")
    print("sample_relations:")
    for relation in dag.relations[:12]:
        print(
            f"  - {relation.from_topic_id} -> {relation.to_topic_id} "
            f"| type={relation.relation_type} | score={relation.score}"
        )
        print(f"    reason={relation.reason}")

    output_path = Path("tmp/topic_dag_smoke.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(dag), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"output_written={output_path}")
    print("smoke_topic_dag passed")


if __name__ == "__main__":
    main()
