import json
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from feature_achievement.db.crud import persist_enriched_chapters
from feature_achievement.db.engine import engine
from feature_achievement.db.models import EnrichedChapter
from feature_achievement.epub.adapter import build_adapter_payload
from feature_achievement.scripts.validate_enriched_v2 import validate_enriched_book

TARGET_VERSION = "v2_indexed_sections_bullets"
UNRESOLVED_OUTPUT = Path("tmp/source_refs_needs_manual.json")

BOOK_SPECS = [
    {
        "book_id": "spring-in-action",
        "epub_dir": Path("book_epub/spring_in_action"),
        "preview_path": Path("tmp/spring_in_action_epub_enriched_preview.json"),
    },
    {
        "book_id": "spring-start-here",
        "epub_dir": Path("book_epub/spring_start_here"),
        "preview_path": Path("tmp/spring_start_here_epub_enriched_preview.json"),
    },
    {
        "book_id": "springboot-in-action",
        "epub_dir": Path("book_epub/springboot_in_action"),
        "preview_path": Path("tmp/springboot_epub_enriched_preview.json"),
    },
]


def _first_epub(epub_dir: Path) -> Path:
    candidates = sorted(epub_dir.glob("*.epub"))
    if not candidates:
        raise FileNotFoundError(f"missing epub under {epub_dir}")
    return candidates[0]


def _build_output_json(book_id: str, payload: dict[str, object]) -> dict[str, object]:
    chapters = payload["chapters"]
    metrics = payload["metrics"]
    unresolved = payload["unresolved_source_refs"]
    parse_status = "ok" if not unresolved else "ok_with_unresolved"
    return {
        "book_id": book_id,
        "chapters": chapters,
        "parse_status": parse_status,
        "parse_metrics": metrics,
        "probe": payload["probe"],
        "unresolved_source_refs": unresolved,
    }


def _write_preview(preview_path: Path, output_json: dict[str, object]) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _collect_books() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    enriched_books: list[dict[str, object]] = []
    unresolved_rows: list[dict[str, object]] = []

    for spec in BOOK_SPECS:
        book_id = spec["book_id"]
        epub_path = _first_epub(spec["epub_dir"])
        payload = build_adapter_payload(epub_path=epub_path, book_id=book_id)
        output_json = _build_output_json(book_id=book_id, payload=payload)
        _write_preview(spec["preview_path"], output_json)

        validation_errors = validate_enriched_book(output_json, source_name=book_id)
        if validation_errors:
            joined = "\n".join(validation_errors)
            raise RuntimeError(f"validation failed for {book_id}:\n{joined}")

        chapters_obj = output_json.get("chapters")
        chapters = chapters_obj if isinstance(chapters_obj, list) else []
        bullet_count = 0
        with_source_refs = 0
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            sections_obj = chapter.get("sections")
            sections = sections_obj if isinstance(sections_obj, list) else []
            for section in sections:
                if not isinstance(section, dict):
                    continue
                bullets_obj = section.get("bullets")
                bullets = bullets_obj if isinstance(bullets_obj, list) else []
                for bullet in bullets:
                    if not isinstance(bullet, dict):
                        continue
                    bullet_count += 1
                    refs_obj = bullet.get("source_refs")
                    refs = refs_obj if isinstance(refs_obj, list) else []
                    if refs:
                        with_source_refs += 1

        print(
            f"prepared {book_id}: chapters={len(chapters)} "
            f"bullets={bullet_count} bullets_with_source_refs={with_source_refs}"
        )
        enriched_books.append(output_json)

        unresolved_obj = output_json.get("unresolved_source_refs")
        unresolved = unresolved_obj if isinstance(unresolved_obj, list) else []
        for row in unresolved:
            if isinstance(row, dict):
                unresolved_rows.append(row)

    return enriched_books, unresolved_rows


def _replace_enriched_chapter_rows(enriched_books: list[dict[str, object]]) -> None:
    with Session(engine) as session:
        before = session.exec(select(EnrichedChapter)).all()
        print(f"existing enriched_chapter rows before rebuild: {len(before)}")
        session.exec(text("DELETE FROM enriched_chapter"))
        session.commit()

    with Session(engine) as session:
        persist_enriched_chapters(
            enriched_books,
            session,
            enrichment_version=TARGET_VERSION,
            overwrite=False,
        )

    with Session(engine) as session:
        after = session.exec(select(EnrichedChapter)).all()
        print(f"enriched_chapter rows after rebuild: {len(after)}")


def _write_unresolved(unresolved_rows: list[dict[str, object]]) -> None:
    UNRESOLVED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    UNRESOLVED_OUTPUT.write_text(
        json.dumps(unresolved_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"unresolved_output={UNRESOLVED_OUTPUT}")
    print(f"unresolved_count={len(unresolved_rows)}")


def main() -> int:
    enriched_books, unresolved_rows = _collect_books()
    _replace_enriched_chapter_rows(enriched_books)
    _write_unresolved(unresolved_rows)
    print(f"target_enrichment_version={TARGET_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
