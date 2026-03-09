import json
import os
import re

ROLE_CHAPTER = "chapter"
ROLE_SECTION = "section"
ROLE_BULLET = "bullet"

CHAPTER_INT = "int"
CHAPTER_CHAPTER = "Chapter"
SECTION_HAS_PAGE = "has_page"
SECTION_NO_PAGE = "no_page"
BULLET_MIX = "mix"
BULLET_SINGLE = "single"

CHAPTER_RULE = {
    "is_numbered_chapter": lambda tokens: tokens[0].isdigit(),
    "is_keyword_chapter": lambda tokens: tokens[0] == "Chapter",
}

SECTION_RULE = {
    "has_page": lambda tokens: tokens[-1].isdigit(),
    "no_page": lambda tokens: not tokens[-1].isdigit(),
}

BULET_RULE = {
    "no_bullet_title": lambda tokens: not tokens[0].replace(".", "").isdigit(),
    "is_single": lambda tokens: tokens[0].count(".") == 2,
}

RULE = {
    "is_chapter": lambda tokens: tokens[0].isdigit() or tokens[0] == "Chapter",
    "is_section": lambda tokens: tokens[0].count(".") == 1,
}


def detect_chapter_type(tokens, rule=CHAPTER_RULE):
    if rule["is_numbered_chapter"](tokens):
        return CHAPTER_INT
    if rule["is_keyword_chapter"](tokens):
        return CHAPTER_CHAPTER
    return None


def detect_section_type(tokens, rule=SECTION_RULE):
    if rule["has_page"](tokens):
        return SECTION_HAS_PAGE
    if rule["no_page"](tokens):
        return SECTION_NO_PAGE
    return None


def detect_bullet_type(tokens, rule=BULET_RULE):
    if rule["no_bullet_title"](tokens):
        return BULLET_MIX
    if rule["is_single"](tokens):
        return BULLET_SINGLE
    return None


def detect_role(tokens, rule=RULE):
    if rule["is_chapter"](tokens):
        return ROLE_CHAPTER
    if rule["is_section"](tokens):
        return ROLE_SECTION
    return ROLE_BULLET


def _normalize_text(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"^\d+\.\d+\.\d+\s+", "", text)
    text = re.sub(r"^\d+\.\d+\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _create_section(chapter: dict, title_raw: str, title_norm: str) -> dict:
    section_order = len(chapter["sections"]) + 1
    section = {
        "section_id": f"{chapter['id']}::s{section_order}",
        "order": section_order,
        "title_raw": title_raw,
        "title_norm": title_norm,
        "bullets": [],
    }
    chapter["sections"].append(section)
    return section


def _append_bullet(section: dict, text_raw: str) -> None:
    text_norm = _normalize_text(text_raw)
    if not text_norm:
        return
    bullet_order = len(section["bullets"]) + 1
    section["bullets"].append(
        {
            "bullet_id": f"{section['section_id']}::b{bullet_order}",
            "order": bullet_order,
            "text_raw": text_raw.strip(),
            "text_norm": text_norm,
            "source_refs": None,
        }
    )


def create_chapter(tokens, book_name, chapters):
    chapter_type = detect_chapter_type(tokens)
    if chapter_type == CHAPTER_INT:
        chapter = {
            "id": f"{book_name}::ch{tokens[0]}",
            "order": int(tokens[0]),
            "title": " ".join(tokens[1:-1]),
            "sections": [],
        }
        chapters.append(chapter)
        return chapter
    if chapter_type == CHAPTER_CHAPTER:
        chapter = {
            "id": f"{book_name}::ch{tokens[1]}",
            "order": int(tokens[1]),
            "title": " ".join(tokens[2:]),
            "sections": [],
        }
        chapters.append(chapter)
        return chapter
    return None


def create_section(chapter, tokens):
    section_type = detect_section_type(tokens)
    if section_type == SECTION_HAS_PAGE:
        title_raw = " ".join(tokens[:-1])
        title_norm = _normalize_text(" ".join(tokens[1:-1]))
        return _create_section(chapter, title_raw=title_raw, title_norm=title_norm)
    if section_type == SECTION_NO_PAGE:
        title_raw = " ".join(tokens)
        title_norm = _normalize_text(" ".join(tokens[1:]))
        return _create_section(chapter, title_raw=title_raw, title_norm=title_norm)
    return None


def _get_or_create_unscoped_section(chapter: dict) -> dict:
    if chapter["sections"]:
        return chapter["sections"][-1]
    return _create_section(
        chapter,
        title_raw=f"{chapter['order']}.0 Unscoped",
        title_norm="unscoped",
    )


def create_bullet(section, tokens, current_bullet):
    bullet_type = detect_bullet_type(tokens)
    if bullet_type == BULLET_MIX:
        for token in tokens:
            if token.isdigit():
                if current_bullet.strip():
                    _append_bullet(section, current_bullet)
                current_bullet = ""
                break
            current_bullet += token + " "
    elif bullet_type == BULLET_SINGLE:
        for token in tokens:
            current_bullet += token + " "
        clean_bullet = " ".join(current_bullet.split()[1:])
        _append_bullet(section, clean_bullet)
        current_bullet = ""

    return current_bullet


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def load_content_to_data(content_path, book_name, rule=RULE):
    """turn path source text to data structure"""
    chapters = []
    content_lines = read_lines(content_path)

    parser_meta = {
        "chapter_types": set(),
        "section_types": set(),
        "bullet_types": set(),
        "rule": "default_v1",
    }

    chapter = None
    current_section = None
    current_bullet = ""

    for line in content_lines:
        line = line.strip()
        if not line:
            continue

        tokens = line.split()
        role = detect_role(tokens, rule)

        if role == ROLE_CHAPTER:
            if chapter is not None and current_section is not None and current_bullet.strip():
                _append_bullet(current_section, current_bullet)
            current_bullet = ""
            chapter_type = detect_chapter_type(tokens)
            if chapter_type is not None:
                parser_meta["chapter_types"].add(chapter_type)
            chapter = create_chapter(tokens, book_name, chapters=chapters)
            current_section = None
        elif role == ROLE_SECTION:
            if chapter is None:
                continue
            if current_section is not None and current_bullet.strip():
                _append_bullet(current_section, current_bullet)
                current_bullet = ""
            section_type = detect_section_type(tokens)
            if section_type is not None:
                parser_meta["section_types"].add(section_type)
            current_section = create_section(chapter, tokens)
        elif role == ROLE_BULLET:
            if chapter is None:
                continue
            bullet_type = detect_bullet_type(tokens)
            if bullet_type is not None:
                parser_meta["bullet_types"].add(bullet_type)
            current_section = current_section or _get_or_create_unscoped_section(chapter)
            current_bullet = create_bullet(current_section, tokens, current_bullet)

    if chapter is not None and current_section is not None and current_bullet.strip():
        _append_bullet(current_section, current_bullet)

    return chapters, parser_meta


def normalize_parser_meta(parser_meta):
    return {
        k: sorted(list(v)) if isinstance(v, set) else v for k, v in parser_meta.items()
    }


def load_data(book_name, chapters, parser_meta):
    data = {
        "book_id": book_name,
        "parser_meta": normalize_parser_meta(parser_meta),
        "chapters": chapters,
    }

    return data


def dump_data_to_json(data, output_dir="output"):
    book_id = data["book_id"]
    path = os.path.join(output_dir, f"{book_id}_enriched.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def convert_content_to_json(book_name, content_path):
    chapters, parser_meta = load_content_to_data(
        content_path=content_path, book_name=book_name
    )
    data = load_data(book_name=book_name, chapters=chapters, parser_meta=parser_meta)
    return data
