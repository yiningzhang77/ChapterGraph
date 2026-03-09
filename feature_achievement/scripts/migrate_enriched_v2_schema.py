from sqlalchemy import text

from feature_achievement.db.engine import engine


def main() -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'enriched_chapter'
                """
            )
        ).all()
        columns = {row[0] for row in rows}

        if not columns:
            print("skip: table 'enriched_chapter' not found")
            return 1

        if "chapter_index_text" not in columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE enriched_chapter
                    ADD COLUMN chapter_index_text TEXT NOT NULL DEFAULT ''
                    """
                )
            )
            print("migrated: added enriched_chapter.chapter_index_text")
        else:
            print("skip: enriched_chapter.chapter_index_text already exists")

        conn.execute(
            text(
                """
                UPDATE enriched_chapter
                SET chapter_index_text = chapter_text
                WHERE chapter_index_text = '' OR chapter_index_text IS NULL
                """
            )
        )
        print("backfilled: chapter_index_text from chapter_text where empty")

        if "signals" in columns:
            conn.execute(text("ALTER TABLE enriched_chapter DROP COLUMN signals"))
            print("migrated: dropped enriched_chapter.signals")
        else:
            print("skip: enriched_chapter.signals already absent")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
