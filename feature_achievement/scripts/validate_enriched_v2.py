import argparse
import json
import os

import yaml


def _validate_bullet(chapter_id: str, section_id: str, idx: int, bullet: object) -> list[str]:
    prefix = f"{chapter_id}/{section_id}/bullet[{idx}]"
    errors: list[str] = []
    if not isinstance(bullet, dict):
        return [f"{prefix}: must be object"]

    required = ["bullet_id", "order", "text_raw", "text_norm", "source_refs"]
    for key in required:
        if key not in bullet:
            errors.append(f"{prefix}: missing '{key}'")

    bullet_id = bullet.get("bullet_id")
    order = bullet.get("order")
    text_raw = bullet.get("text_raw")
    text_norm = bullet.get("text_norm")
    source_refs = bullet.get("source_refs")

    if not isinstance(bullet_id, str) or not bullet_id.strip():
        errors.append(f"{prefix}: bullet_id must be non-empty string")
    if not isinstance(order, int):
        errors.append(f"{prefix}: order must be int")
    if not isinstance(text_raw, str):
        errors.append(f"{prefix}: text_raw must be string")
    if not isinstance(text_norm, str):
        errors.append(f"{prefix}: text_norm must be string")
    if source_refs is not None and not isinstance(source_refs, list):
        errors.append(f"{prefix}: source_refs must be null or list")

    return errors


def _validate_section(chapter_id: str, idx: int, section: object) -> list[str]:
    prefix = f"{chapter_id}/section[{idx}]"
    errors: list[str] = []
    if not isinstance(section, dict):
        return [f"{prefix}: must be object"]

    required = ["section_id", "order", "title_raw", "title_norm", "bullets"]
    for key in required:
        if key not in section:
            errors.append(f"{prefix}: missing '{key}'")

    section_id = section.get("section_id")
    order = section.get("order")
    title_raw = section.get("title_raw")
    title_norm = section.get("title_norm")
    bullets = section.get("bullets")

    if not isinstance(section_id, str) or not section_id.strip():
        errors.append(f"{prefix}: section_id must be non-empty string")
    if not isinstance(order, int):
        errors.append(f"{prefix}: order must be int")
    if not isinstance(title_raw, str):
        errors.append(f"{prefix}: title_raw must be string")
    if not isinstance(title_norm, str):
        errors.append(f"{prefix}: title_norm must be string")
    if not isinstance(bullets, list):
        errors.append(f"{prefix}: bullets must be list")
    else:
        for bullet_idx, bullet in enumerate(bullets, start=1):
            errors.extend(_validate_bullet(chapter_id, section_id if isinstance(section_id, str) else "invalid", bullet_idx, bullet))

    return errors


def validate_enriched_book(data: dict[str, object], source_name: str = "") -> list[str]:
    errors: list[str] = []
    prefix = source_name or "book"

    book_id = data.get("book_id")
    chapters = data.get("chapters")
    if not isinstance(book_id, str) or not book_id.strip():
        errors.append(f"{prefix}: missing/invalid book_id")
    if not isinstance(chapters, list):
        errors.append(f"{prefix}: chapters must be list")
        return errors

    for chapter_idx, chapter in enumerate(chapters, start=1):
        chapter_prefix = f"{prefix}/chapter[{chapter_idx}]"
        if not isinstance(chapter, dict):
            errors.append(f"{chapter_prefix}: must be object")
            continue

        for key in ["id", "title", "chapter_index_text", "chapter_text", "sections"]:
            if key not in chapter:
                errors.append(f"{chapter_prefix}: missing '{key}'")

        chapter_id = chapter.get("id")
        sections = chapter.get("sections")
        chapter_index_text = chapter.get("chapter_index_text")

        if "signals" in chapter:
            errors.append(f"{chapter_prefix}: 'signals' must not exist")
        if not isinstance(chapter_id, str) or not chapter_id.strip():
            errors.append(f"{chapter_prefix}: id must be non-empty string")
            chapter_id = "invalid"
        if not isinstance(chapter_index_text, str) or not chapter_index_text.strip():
            errors.append(f"{chapter_prefix}: chapter_index_text must be non-empty string")
        if not isinstance(sections, list):
            errors.append(f"{chapter_prefix}: sections must be list")
            continue

        for section_idx, section in enumerate(sections, start=1):
            errors.extend(_validate_section(chapter_id, section_idx, section))

    return errors


def _iter_book_paths(config_path: str, output_dir: str) -> list[str]:
    with open(config_path, "r", encoding="utf-8") as f:
        book_configs = yaml.safe_load(f) or []
    paths: list[str] = []
    for cfg in book_configs:
        book_name = cfg.get("book_name")
        if not isinstance(book_name, str):
            continue
        paths.append(os.path.join(output_dir, f"{book_name}_enriched.json"))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enriched JSON files against v2 schema.")
    parser.add_argument("--config", default="book_content/books.yaml")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Explicit enriched JSON path. Can be passed multiple times.",
    )
    args = parser.parse_args()

    paths = args.input if args.input else _iter_book_paths(args.config, args.output_dir)
    if not paths:
        print("no books found in config")
        return 1

    all_errors: list[str] = []
    for path in paths:
        if not os.path.exists(path):
            all_errors.append(f"{path}: file not found")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            all_errors.append(f"{path}: root must be object")
            continue
        all_errors.extend(validate_enriched_book(data, source_name=path))

    if all_errors:
        print("enriched v2 validation failed")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("enriched v2 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
