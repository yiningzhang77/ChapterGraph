import argparse
import json
import os
from collections.abc import Iterator

import yaml
from sqlmodel import Session

from feature_achievement.db.crud import persist_enriched_chapters
from feature_achievement.db.engine import engine
from feature_achievement.scripts.validate_enriched_v2 import validate_enriched_book


def load_json(path: str) -> dict[str, object]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be object")
    return data


def iter_enriched_books(config_path: str, output_dir: str) -> Iterator[dict[str, object]]:
    with open(config_path, "r", encoding="utf-8") as f:
        book_configs = yaml.safe_load(f) or []

    for cfg in book_configs:
        book_id = cfg["book_name"]
        json_path = os.path.join(output_dir, f"{book_id}_enriched.json")
        if not os.path.exists(json_path):
            print(f"skip: {json_path} not found")
            continue
        yield load_json(json_path)


def iter_enriched_books_from_inputs(
    input_paths: list[str],
) -> Iterator[dict[str, object]]:
    for input_path in input_paths:
        if not os.path.exists(input_path):
            print(f"skip: {input_path} not found")
            continue
        yield load_json(input_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import enriched chapters from output JSON into DB.",
    )
    parser.add_argument("--config", default="book_content/books.yaml")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Explicit enriched JSON path. Can be passed multiple times.",
    )
    parser.add_argument("--enrichment-version", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.input:
        enriched_books = list(iter_enriched_books_from_inputs(args.input))
    else:
        enriched_books = list(iter_enriched_books(args.config, args.output_dir))

    if not enriched_books:
        print("No enriched JSON found. Run enrichment first.")
        return 1

    validation_errors: list[str] = []
    for book in enriched_books:
        validation_errors.extend(
            validate_enriched_book(book, source_name=str(book.get("book_id", "unknown")))
        )
    if validation_errors:
        print("validation failed: enriched JSON is not v2 compatible")
        for error in validation_errors:
            print(f"- {error}")
        return 1

    with Session(engine) as session:
        persist_enriched_chapters(
            enriched_books,
            session,
            enrichment_version=args.enrichment_version,
            overwrite=args.overwrite,
        )

    print(f"Imported enriched chapters for {len(enriched_books)} books.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
