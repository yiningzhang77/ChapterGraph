from functools import lru_cache
from dataclasses import dataclass

from feature_achievement.enrichment import load_all_enriched_data
from feature_achievement.retrieval.utils.text import collect_chapter_texts
from feature_achievement.db.engine import get_session


@dataclass(frozen=True)
class RetrievalResources:
    enriched_books: list[dict]
    chapter_texts: dict[str, str]


@lru_cache
def get_retrieval_resources() -> RetrievalResources:
    enriched_books = load_all_enriched_data("book_content/books.yaml")
    chapter_texts = collect_chapter_texts(enriched_books)
    return RetrievalResources(
        enriched_books=enriched_books,
        chapter_texts=chapter_texts,
    )


def get_db():
    yield from get_session()
