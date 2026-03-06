from sqlalchemy import text

from feature_achievement.db.engine import engine


def migrate_run_min_store_to_min_score() -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'run'
                """
            )
        ).all()
        columns = {row[0] for row in rows}

        if not columns:
            print("skip: table 'run' not found")
            return 0

        if "min_score" in columns and "min_store" not in columns:
            print("skip: 'run.min_score' already exists")
            return 0

        if "min_store" in columns and "min_score" not in columns:
            conn.execute(text('ALTER TABLE "run" RENAME COLUMN min_store TO min_score'))
            print("migrated: renamed 'run.min_store' to 'run.min_score'")
            return 0

        if "min_store" in columns and "min_score" in columns:
            print("skip: both 'min_store' and 'min_score' exist; manual cleanup required")
            return 1

        print("skip: neither 'min_store' nor 'min_score' found")
        return 1


if __name__ == "__main__":
    raise SystemExit(migrate_run_min_store_to_min_score())
