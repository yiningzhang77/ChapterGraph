import argparse
import os

import yaml

from feature_achievement.enrichment import enrich_chapter_text
from feature_achievement.ingestion import convert_content_to_json, dump_data_to_json
from feature_achievement.scripts.validate_enriched_v2 import validate_enriched_book


def _iter_book_configs(config_path: str) -> list[dict[str, object]]:
    with open(config_path, "r", encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    return [item for item in items if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate enriched JSON files to v2 shape (sections[].bullets[], chapter_index_text).",
    )
    parser.add_argument("--config", default="book_content/books.yaml")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    book_configs = _iter_book_configs(args.config)
    if not book_configs:
        print("no book configs found")
        return 1

    errors: list[str] = []
    written_files: list[str] = []

    for cfg in book_configs:
        book_name = cfg.get("book_name")
        content_path = cfg.get("content_path")
        if not isinstance(book_name, str) or not isinstance(content_path, str):
            errors.append(f"invalid config entry: {cfg}")
            continue
        if not os.path.exists(content_path):
            errors.append(f"{book_name}: content path not found: {content_path}")
            continue

        raw_data = convert_content_to_json(book_name, content_path)
        enriched_data = enrich_chapter_text(raw_data)
        file_errors = validate_enriched_book(
            enriched_data,
            source_name=f"{book_name}(generated)",
        )
        if file_errors:
            errors.extend(file_errors)
            continue

        dump_data_to_json(enriched_data, output_dir=args.output_dir)
        written_files.append(os.path.join(args.output_dir, f"{book_name}_enriched.json"))

    if errors:
        print("failed to migrate enriched files to v2 shape")
        for error in errors:
            print(f"- {error}")
        return 1

    print("migrated enriched files to v2 shape")
    for file_path in written_files:
        print(f"- {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
