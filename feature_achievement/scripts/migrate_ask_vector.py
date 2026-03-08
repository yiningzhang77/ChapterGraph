from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from feature_achievement.db.engine import engine


def main() -> int:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        """
        CREATE TABLE IF NOT EXISTS enriched_chapter_embedding (
            chapter_id TEXT PRIMARY KEY REFERENCES enriched_chapter(id) ON DELETE CASCADE,
            enrichment_version TEXT NOT NULL,
            embedding vector(384) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_enriched_chapter_embedding_enrichment_version
        ON enriched_chapter_embedding (enrichment_version)
        """,
    ]

    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except SQLAlchemyError as error:
        print("failed to migrate ask vector schema")
        print(str(error))
        print(
            "hint: install pgvector on PostgreSQL server first, then rerun "
            "python -m feature_achievement.scripts.migrate_ask_vector"
        )
        return 1

    print("ask vector schema migrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
