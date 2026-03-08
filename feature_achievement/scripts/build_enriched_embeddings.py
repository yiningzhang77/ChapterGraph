import argparse
from collections.abc import Sequence

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from feature_achievement.db.engine import engine
from feature_achievement.db.models import EnrichedChapter

EXPECTED_DIMENSION = 384


def vector_to_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and upsert chapter embeddings for ask vector search.",
    )
    parser.add_argument(
        "--enrichment-version",
        default="v1_bullets+sections",
        help="Filter EnrichedChapter rows by enrichment_version.",
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="SentenceTransformer model name.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding model batch size.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with engine.connect() as conn:
        table_name = conn.execute(
            text("SELECT to_regclass('public.enriched_chapter_embedding')")
        ).scalar()
    if table_name is None:
        print("enriched_chapter_embedding table not found")
        print(
            "run migration first: "
            "python -m feature_achievement.scripts.migrate_ask_vector"
        )
        return 1

    with Session(engine) as session:
        rows = session.exec(
            select(EnrichedChapter).where(
                EnrichedChapter.enrichment_version == args.enrichment_version
            )
        ).all()

    if not rows:
        print(
            "No enriched chapters found for enrichment_version="
            f"{args.enrichment_version}"
        )
        return 1

    chapter_ids = [row.id for row in rows]
    chapter_texts = [row.chapter_text or "" for row in rows]

    model = SentenceTransformer(args.model)
    embeddings = model.encode(
        chapter_texts,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    if len(embeddings) != len(chapter_ids):
        raise RuntimeError("embedding count does not match chapter count")

    dimension = len(embeddings[0]) if len(embeddings) > 0 else 0
    if dimension != EXPECTED_DIMENSION:
        raise RuntimeError(
            f"embedding dimension mismatch: expected {EXPECTED_DIMENSION}, got {dimension}"
        )

    payloads: list[dict[str, str]] = []
    for chapter_id, embedding in zip(chapter_ids, embeddings):
        embedding_values = embedding.tolist()
        payloads.append(
            {
                "chapter_id": chapter_id,
                "enrichment_version": args.enrichment_version,
                "embedding": vector_to_literal(embedding_values),
            }
        )

    upsert_sql = text(
        """
        INSERT INTO enriched_chapter_embedding (
            chapter_id,
            enrichment_version,
            embedding
        )
        VALUES (
            :chapter_id,
            :enrichment_version,
            CAST(:embedding AS vector)
        )
        ON CONFLICT (chapter_id) DO UPDATE
        SET enrichment_version = EXCLUDED.enrichment_version,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
        """
    )

    try:
        with engine.begin() as conn:
            conn.execute(upsert_sql, payloads)
    except SQLAlchemyError as error:
        print("failed to upsert enriched chapter embeddings")
        print(str(error))
        return 1

    print(f"embedded chapters: {len(payloads)}")
    print(f"enrichment_version: {args.enrichment_version}")
    print(f"model: {args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
