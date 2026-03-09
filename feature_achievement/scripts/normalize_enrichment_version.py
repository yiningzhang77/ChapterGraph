from sqlalchemy import text

from feature_achievement.db.engine import engine

TARGET_VERSION = "v2_indexed_sections_bullets"


def main() -> int:
    with engine.begin() as conn:
        enriched_result = conn.execute(
            text(
                """
                UPDATE enriched_chapter
                SET enrichment_version = :target
                WHERE enrichment_version IS NULL
                   OR enrichment_version IN ('v1_test', 'v1', 'v1_bullets+sections')
                """
            ),
            {"target": TARGET_VERSION},
        )

        run_result = conn.execute(
            text(
                """
                UPDATE run
                SET enrichment_version = :target
                WHERE enrichment_version IS NULL
                   OR enrichment_version <> :target
                """
            ),
            {"target": TARGET_VERSION},
        )

    print(f"normalized enriched_chapter rows: {enriched_result.rowcount}")
    print(f"normalized run rows: {run_result.rowcount}")
    print(f"target enrichment_version: {TARGET_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
