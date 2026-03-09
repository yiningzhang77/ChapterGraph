import argparse
import json
import os

import yaml

from feature_achievement.scripts.validate_enriched_v2 import validate_enriched_book


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check for enriched v2 output files.")
    parser.add_argument("--config", default="book_content/books.yaml")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        configs = yaml.safe_load(f) or []

    errors: list[str] = []
    total_books = 0
    total_chapters = 0
    total_sections = 0
    total_bullets = 0

    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        book_name = cfg.get("book_name")
        if not isinstance(book_name, str):
            continue
        total_books += 1
        path = os.path.join(args.output_dir, f"{book_name}_enriched.json")
        if not os.path.exists(path):
            errors.append(f"{path}: file not found")
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            errors.append(f"{path}: root must be object")
            continue

        errors.extend(validate_enriched_book(data, source_name=path))
        chapters = data.get("chapters")
        if not isinstance(chapters, list):
            continue
        total_chapters += len(chapters)
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            sections = chapter.get("sections")
            if not isinstance(sections, list):
                continue
            total_sections += len(sections)
            for section in sections:
                if not isinstance(section, dict):
                    continue
                bullets = section.get("bullets")
                if isinstance(bullets, list):
                    total_bullets += len(bullets)

    if errors:
        print("smoke_enriched_v2 failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("smoke_enriched_v2 passed")
    print(f"books={total_books}")
    print(f"chapters={total_chapters}")
    print(f"sections={total_sections}")
    print(f"bullets={total_bullets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
