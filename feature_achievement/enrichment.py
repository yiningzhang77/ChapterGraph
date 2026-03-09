import json
import os
import re
import unicodedata

from feature_achievement.ingestion import convert_content_to_json, dump_data_to_json
import yaml


def _normalize_for_index(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.lower().strip()
    text = re.sub(r"^\d+\.\d+\.\d+\s+", "", text)
    text = re.sub(r"^\d+\.\d+\s+", "", text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _section_title_norm(section: object) -> str:
    if isinstance(section, dict):
        value = section.get("title_norm")
        if isinstance(value, str) and value.strip():
            return value
        raw_value = section.get("title_raw")
        if isinstance(raw_value, str):
            return _normalize_for_index(raw_value)
        return ""
    if isinstance(section, str):
        return _normalize_for_index(section)
    return ""


def _iter_section_bullets(section: object) -> list[dict[str, object]]:
    if isinstance(section, dict):
        bullets = section.get("bullets")
        if isinstance(bullets, list):
            return [entry for entry in bullets if isinstance(entry, dict)]
    return []


def _bullet_text_norm(bullet: dict[str, object]) -> str:
    norm_value = bullet.get("text_norm")
    if isinstance(norm_value, str) and norm_value.strip():
        return norm_value
    raw_value = bullet.get("text_raw")
    if isinstance(raw_value, str):
        return _normalize_for_index(raw_value)
    return ""


def _build_chapter_index_text(book_id: str, chapter: dict[str, object]) -> str:
    chapter_id = chapter.get("id")
    chapter_title = chapter.get("title")
    parts = [
        f"book:{_normalize_for_index(book_id)}",
        f"chapter:{_normalize_for_index(chapter_id if isinstance(chapter_id, str) else '')}",
        f"title:{_normalize_for_index(chapter_title if isinstance(chapter_title, str) else '')}",
    ]

    sections = chapter.get("sections")
    section_items = sections if isinstance(sections, list) else []

    has_bullets = False
    for section in section_items:
        section_norm = _section_title_norm(section)
        if section_norm:
            parts.append(f"section:{section_norm}")

        for bullet in _iter_section_bullets(section):
            bullet_norm = _bullet_text_norm(bullet)
            if bullet_norm:
                parts.append(f"bullet:{bullet_norm}")
                has_bullets = True

    if not has_bullets:
        parts.append("bullet:none")

    return " ".join(parts)


def enrich_chapter_text(data: dict) -> dict:
    book_id = data.get("book_id")
    if not isinstance(book_id, str):
        book_id = ""

    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        return data

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_index_text = _build_chapter_index_text(book_id, chapter)
        chapter["chapter_index_text"] = chapter_index_text
        chapter["chapter_text"] = chapter_index_text
        if "signals" in chapter:
            chapter.pop("signals", None)

    return data


def load_enriched_json(book_name, output_dir="output"):
    path = os.path.join(output_dir, f"{book_name}_enriched.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_enriched_data(book_name, content_path, output_dir="output", prefer_output=True):
    if prefer_output:
        cached = load_enriched_json(book_name, output_dir=output_dir)
        if cached:
            return cached

    base_data = convert_content_to_json(book_name, content_path)
    enriched_data = enrich_chapter_text(base_data)
    dump_data_to_json(enriched_data, output_dir=output_dir)
    return enriched_data


def load_all_enriched_data(config_path, output_dir="output", prefer_output=True):
    with open(config_path, "r") as f:
        book_configs = yaml.safe_load(f)
    enriched_books = []

    for cfg in book_configs:
        enriched = load_enriched_data(
            book_name=cfg["book_name"],
            content_path=cfg["content_path"],
            output_dir=output_dir,
            prefer_output=prefer_output,
        )
        enriched_books.append(enriched)

    return enriched_books
