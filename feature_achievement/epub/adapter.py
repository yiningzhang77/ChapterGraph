from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict
from zipfile import ZipFile

from feature_achievement.epub.outline import TocNode, extract_outline
from feature_achievement.epub.probe import ProbeResult, probe_epub
from feature_achievement.epub.source_refs import build_source_refs_with_fallback

_CHAPTER_PREFIX_RE = re.compile(r"^\s*(\d+)\s+")
_SECTION_PREFIX_RE = re.compile(r"^\s*(\d+\.\d+)\s+")
_BULLET_PREFIX_RE = re.compile(r"^\s*(\d+\.\d+\.\d+)\s+")
_SECTION_NUMERIC_RE = re.compile(r"^\s*(\d+)\.(\d+)\b")
_BULLET_NUMERIC_RE = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\b")
_APPENDIX_WORD_RE = re.compile(r"^\s*appendix\b", re.IGNORECASE)
_APPENDIX_LETTER_RE = re.compile(r"^\s*[A-Z](?:\b|[.:]\s)")
_SECTION_ID_RE = re.compile(r"::ch(\d+)::s(\d+)$")


class ParseMetrics(TypedDict):
    total_outline_nodes: int
    chapter_count: int
    section_count: int
    bullet_count: int
    bullets_with_source_refs: int
    unresolved_source_refs: int


class AdaptedPayload(TypedDict):
    probe: dict[str, object]
    chapters: list[dict[str, object]]
    metrics: ParseMetrics
    unresolved_source_refs: list[dict[str, object]]


@dataclass(frozen=True)
class _OutlineEntry:
    index: int
    node: TocNode
    kind: str


def _normalize_for_index(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.lower().strip()
    text = re.sub(r"^\d+\.\d+\.\d+\s+", "", text)
    text = re.sub(r"^\d+\.\d+\s+", "", text)
    text = re.sub(r"^\d+\s+", "", text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _section_title_norm(section: dict[str, object]) -> str:
    value = section.get("title_norm")
    if isinstance(value, str) and value.strip():
        return value
    raw = section.get("title_raw")
    if isinstance(raw, str):
        return _normalize_for_index(raw)
    return ""


def _bullet_text_norm(bullet: dict[str, object]) -> str:
    value = bullet.get("text_norm")
    if isinstance(value, str) and value.strip():
        return value
    raw = bullet.get("text_raw")
    if isinstance(raw, str):
        return _normalize_for_index(raw)
    return ""


def _build_chapter_index_text(book_id: str, chapter: dict[str, object]) -> str:
    chapter_id = chapter.get("id")
    chapter_title = chapter.get("title")
    parts = [
        f"book:{_normalize_for_index(book_id)}",
        f"chapter:{_normalize_for_index(chapter_id if isinstance(chapter_id, str) else '')}",
        f"title:{_normalize_for_index(chapter_title if isinstance(chapter_title, str) else '')}",
    ]

    sections_obj = chapter.get("sections")
    sections = sections_obj if isinstance(sections_obj, list) else []
    has_bullets = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_norm = _section_title_norm(section)
        if section_norm:
            parts.append(f"section:{section_norm}")
        bullets_obj = section.get("bullets")
        bullets = bullets_obj if isinstance(bullets_obj, list) else []
        for bullet in bullets:
            if not isinstance(bullet, dict):
                continue
            bullet_norm = _bullet_text_norm(bullet)
            if bullet_norm:
                parts.append(f"bullet:{bullet_norm}")
                has_bullets = True

    if not has_bullets:
        parts.append("bullet:none")
    return " ".join(parts)


def _is_chapter_title(title: str, include_appendix: bool) -> bool:
    if _CHAPTER_PREFIX_RE.match(title):
        return True
    if include_appendix and (
        _APPENDIX_WORD_RE.match(title) or _APPENDIX_LETTER_RE.match(title)
    ):
        return True
    return False


def _classify_node(node: TocNode, include_appendix: bool) -> str:
    title = node.title.strip()
    if _BULLET_PREFIX_RE.match(title):
        return "bullet"
    if _SECTION_PREFIX_RE.match(title):
        return "section"
    if _is_chapter_title(title, include_appendix=include_appendix):
        return "chapter"
    if node.level >= 3:
        return "bullet"
    if node.level == 2:
        return "section"
    return "ignore"


def _next_anchor(entries: list[_OutlineEntry], current_index: int, href_file: str) -> str | None:
    for entry in entries:
        if entry.index <= current_index:
            continue
        if entry.node.href_file != href_file:
            continue
        if entry.node.href_anchor:
            return entry.node.href_anchor
    return None


def _ensure_section(
    *,
    chapter: dict[str, object],
    chapter_order: int,
    href_file: str,
    href_anchor: str | None,
    node_index: int,
) -> dict[str, object]:
    sections_obj = chapter.get("sections")
    sections = sections_obj if isinstance(sections_obj, list) else []
    if sections:
        last = sections[-1]
        if isinstance(last, dict):
            return last

    section_order = 1
    section_id = f"{chapter['id']}::s{section_order}"
    section: dict[str, object] = {
        "section_id": section_id,
        "order": section_order,
        "title_raw": f"{chapter_order}.0",
        "title_norm": "",
        "bullets": [],
        "_meta_href_file": href_file,
        "_meta_start_anchor": href_anchor,
        "_meta_node_index": node_index,
    }
    sections.append(section)
    chapter["sections"] = sections
    return section


def _section_id_numbers(section_id: str) -> tuple[int, int] | None:
    match = _SECTION_ID_RE.search(section_id)
    if match is None:
        return None
    chapter_number = int(match.group(1))
    section_number = int(match.group(2))
    return chapter_number, section_number


def _bullet_heading_numbers(text_raw: str) -> tuple[int, int, int] | None:
    match = _BULLET_NUMERIC_RE.match(text_raw)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _section_heading_numbers(title_raw: str) -> tuple[int, int] | None:
    match = _SECTION_NUMERIC_RE.match(title_raw)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _normalize_section_bullets(section: dict[str, object]) -> None:
    section_id_obj = section.get("section_id")
    if not isinstance(section_id_obj, str):
        return
    section_numbers = _section_id_numbers(section_id_obj)
    if section_numbers is None:
        return

    bullets_obj = section.get("bullets")
    bullets = bullets_obj if isinstance(bullets_obj, list) else []
    if not bullets:
        return

    chapter_number, section_number = section_numbers
    has_matching_numeric = False
    filtered_bullets: list[dict[str, object]] = []
    for bullet in bullets:
        if not isinstance(bullet, dict):
            continue
        text_raw_obj = bullet.get("text_raw")
        text_raw = text_raw_obj if isinstance(text_raw_obj, str) else ""
        numeric = _bullet_heading_numbers(text_raw)
        if numeric is None:
            continue
        if numeric[0] != chapter_number or numeric[1] != section_number:
            continue
        has_matching_numeric = True
        filtered_bullets.append(bullet)

    if has_matching_numeric and filtered_bullets:
        bullets = filtered_bullets

    normalized: list[dict[str, object]] = []
    for index, bullet in enumerate(bullets, start=1):
        if not isinstance(bullet, dict):
            continue
        bullet["order"] = index
        bullet["bullet_id"] = f"{section_id_obj}::b{index}"
        normalized.append(bullet)
    section["bullets"] = normalized


def build_adapter_payload(
    epub_path: str | Path,
    book_id: str,
    *,
    include_appendix: bool = False,
) -> AdaptedPayload:
    probe_result: ProbeResult = probe_epub(epub_path)
    outline_nodes = extract_outline(epub_path, probe_result)
    entries = [
        _OutlineEntry(
            index=index,
            node=node,
            kind=_classify_node(node, include_appendix=include_appendix),
        )
        for index, node in enumerate(outline_nodes)
    ]

    chapters: list[dict[str, object]] = []
    unresolved_source_refs: list[dict[str, object]] = []
    chapter_count = 0

    current_chapter: dict[str, object] | None = None
    current_section: dict[str, object] | None = None

    with ZipFile(Path(epub_path)) as zip_file:
        for entry in entries:
            node = entry.node
            if entry.kind == "chapter":
                chapter_count += 1
                chapter_id = f"{book_id}::ch{chapter_count}"
                current_chapter = {
                    "id": chapter_id,
                    "title": node.title,
                    "sections": [],
                }
                chapters.append(current_chapter)
                current_section = None
                continue

            if current_chapter is None:
                continue

            if entry.kind == "section":
                sections_obj = current_chapter.get("sections")
                sections = sections_obj if isinstance(sections_obj, list) else []
                local_order = len(sections) + 1
                section_order = local_order
                heading_numbers = _section_heading_numbers(node.title)
                if heading_numbers is not None and heading_numbers[0] == chapter_count:
                    used_orders = {
                        section.get("order")
                        for section in sections
                        if isinstance(section, dict)
                        and isinstance(section.get("order"), int)
                    }
                    candidate_order = heading_numbers[1]
                    if candidate_order >= 1 and candidate_order not in used_orders:
                        section_order = candidate_order
                section = {
                    "section_id": f"{current_chapter['id']}::s{section_order}",
                    "order": section_order,
                    "title_raw": node.title,
                    "title_norm": _normalize_for_index(node.title),
                    "bullets": [],
                    "_meta_href_file": node.href_file,
                    "_meta_start_anchor": node.href_anchor,
                    "_meta_node_index": entry.index,
                }
                sections.append(section)
                current_chapter["sections"] = sections
                current_section = section
                continue

            if entry.kind != "bullet":
                continue

            if current_section is None:
                current_section = _ensure_section(
                    chapter=current_chapter,
                    chapter_order=chapter_count,
                    href_file=node.href_file,
                    href_anchor=node.href_anchor,
                    node_index=entry.index,
                )

            bullets_obj = current_section.get("bullets")
            bullets = bullets_obj if isinstance(bullets_obj, list) else []
            bullet_order = len(bullets) + 1
            bullet_id = f"{current_section['section_id']}::b{bullet_order}"

            section_start_anchor_obj = current_section.get("_meta_start_anchor")
            section_start_anchor = (
                section_start_anchor_obj if isinstance(section_start_anchor_obj, str) else None
            )
            section_end_anchor = _next_anchor(
                entries,
                current_section.get("_meta_node_index", entry.index)
                if isinstance(current_section.get("_meta_node_index"), int)
                else entry.index,
                current_section.get("_meta_href_file", node.href_file)
                if isinstance(current_section.get("_meta_href_file"), str)
                else node.href_file,
            )

            bullet_end_anchor = _next_anchor(entries, entry.index, node.href_file)
            refs, mode = build_source_refs_with_fallback(
                zip_file=zip_file,
                file_path=node.href_file,
                bullet_start_anchor=node.href_anchor or "",
                bullet_end_anchor=bullet_end_anchor,
                section_start_anchor=section_start_anchor,
                section_end_anchor=section_end_anchor,
            ) if node.href_anchor else (None, "unresolved")

            if refs is None:
                unresolved_source_refs.append(
                    {
                        "chapter_id": current_chapter["id"],
                        "section_id": current_section["section_id"],
                        "bullet_id": bullet_id,
                        "file": node.href_file,
                        "start_anchor": node.href_anchor,
                        "end_anchor": bullet_end_anchor,
                        "reason": mode,
                    }
                )

            bullet: dict[str, object] = {
                "bullet_id": bullet_id,
                "order": bullet_order,
                "text_raw": node.title,
                "text_norm": _normalize_for_index(node.title),
                "source_refs": refs,
            }
            bullets.append(bullet)
            current_section["bullets"] = bullets

    for chapter in chapters:
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        cleaned_sections: list[dict[str, object]] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            section.pop("_meta_href_file", None)
            section.pop("_meta_start_anchor", None)
            section.pop("_meta_node_index", None)
            _normalize_section_bullets(section)
            cleaned_sections.append(section)
        chapter["sections"] = cleaned_sections
        chapter_index_text = _build_chapter_index_text(book_id, chapter)
        chapter["chapter_index_text"] = chapter_index_text
        chapter["chapter_text"] = chapter_index_text

    computed_section_count = 0
    computed_bullet_count = 0
    computed_bullets_with_source_refs = 0
    for chapter in chapters:
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        computed_section_count += len(sections)
        for section in sections:
            if not isinstance(section, dict):
                continue
            bullets_obj = section.get("bullets")
            bullets = bullets_obj if isinstance(bullets_obj, list) else []
            computed_bullet_count += len(bullets)
            for bullet in bullets:
                if not isinstance(bullet, dict):
                    continue
                refs_obj = bullet.get("source_refs")
                refs = refs_obj if isinstance(refs_obj, list) else []
                if refs:
                    computed_bullets_with_source_refs += 1

    metrics: ParseMetrics = {
        "total_outline_nodes": len(entries),
        "chapter_count": len(chapters),
        "section_count": computed_section_count,
        "bullet_count": computed_bullet_count,
        "bullets_with_source_refs": computed_bullets_with_source_refs,
        "unresolved_source_refs": len(unresolved_source_refs),
    }

    return {
        "probe": probe_result.as_dict(),
        "chapters": chapters,
        "metrics": metrics,
        "unresolved_source_refs": unresolved_source_refs,
    }
