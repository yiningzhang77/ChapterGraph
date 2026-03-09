from typing import Optional

from feature_achievement.db.models import Book, Chapter, Edge, Run, EnrichedChapter


def persist_books_and_chapters(enriched_books, session):
    """
    Persist books and chapters into database.
    Assumes enriched_books structure:
    {
        "book_id": str,
        "chapters": [...]
    }
    """

    for book in enriched_books:
        book_id = book["book_id"]
        chapters = book["chapters"]
        existing = session.get(Book, book_id)
        if not existing:
            # 1️⃣ persist Book
            session.add(Book(id=book_id, title=book_id, size=len(chapters)))

        # 2️⃣ persist Chapters
        for ch in book["chapters"]:
            if not session.get(Chapter, ch["id"]):
                session.add(
                    Chapter(
                        id=ch["id"],
                        book_id=book_id,
                        title=ch.get("title"),
                        chapter_text=ch["chapter_text"],
                    )
                )

    session.commit()


def persist_edges(edges, run_id: int, session):
    for e in edges:
        session.add(
            Edge(
                run_id=run_id,
                from_chapter=e["from"],
                to_chapter=e["to"],
                score=e["score"],
                type=e["type"],
            )
        )
    session.commit()


def persist_enriched_chapters(
    enriched_books,
    session,
    enrichment_version: Optional[str] = None,
    overwrite: bool = False,
):
    """
    Persist enriched chapters (from enrichment JSON) into database.
    """
    for book in enriched_books:
        book_id = book["book_id"]
        chapters = book.get("chapters", [])

        existing_book = session.get(Book, book_id)
        if not existing_book:
            session.add(Book(id=book_id, title=book_id, size=len(chapters)))

        for ch in chapters:
            existing = session.get(EnrichedChapter, ch["id"])
            if existing and not overwrite:
                continue

            payload = {
                "id": ch["id"],
                "book_id": book_id,
                "order": ch.get("order"),
                "title": ch.get("title"),
                "chapter_text": ch.get("chapter_text", ""),
                "chapter_index_text": ch.get("chapter_index_text", ch.get("chapter_text", "")),
                "sections": ch.get("sections", []),
                "enrichment_version": enrichment_version,
            }

            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                session.add(EnrichedChapter(**payload))

    session.commit()
