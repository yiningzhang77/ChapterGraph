from pathlib import Path
import re

import pytest

from feature_achievement.epub.adapter import build_adapter_payload


def _first_epub(folder: str) -> Path:
    root = Path("book_epub") / folder
    if not root.exists():
        pytest.skip(f"missing sample folder: {root}")
    candidates = sorted(root.glob("*.epub"))
    if not candidates:
        pytest.skip(f"missing sample epub in: {root}")
    return candidates[0]


def test_adapter_returns_probe_metrics_and_chapter_payload() -> None:
    epub_path = _first_epub("spring_start_here")
    payload = build_adapter_payload(epub_path=epub_path, book_id="spring-start-here")

    probe = payload["probe"]
    assert probe["content_layout_type"] == "type_b_chapter_files"
    assert probe["selected_strategy"] == "strategy_type_b_chapter_files"

    chapters = payload["chapters"]
    assert len(chapters) >= 10
    first_chapter = chapters[0]
    assert "id" in first_chapter
    assert "title" in first_chapter
    assert "chapter_index_text" in first_chapter
    assert "sections" in first_chapter

    metrics = payload["metrics"]
    assert metrics["total_outline_nodes"] > 0
    assert metrics["chapter_count"] == len(chapters)
    assert metrics["section_count"] >= 1
    assert metrics["bullet_count"] >= 1


def test_adapter_outputs_unresolved_list_structure() -> None:
    epub_path = _first_epub("springboot_in_action")
    payload = build_adapter_payload(epub_path=epub_path, book_id="springboot-in-action")

    unresolved = payload["unresolved_source_refs"]
    assert isinstance(unresolved, list)
    if unresolved:
        sample = unresolved[0]
        assert "chapter_id" in sample
        assert "section_id" in sample
        assert "bullet_id" in sample
        assert "reason" in sample


def test_adapter_default_keeps_main_numbered_chapters_only() -> None:
    spring_in_action_path = _first_epub("spring_in_action")
    springboot_path = _first_epub("springboot_in_action")

    payload_a = build_adapter_payload(
        epub_path=spring_in_action_path,
        book_id="spring-in-action",
    )
    payload_b = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )

    assert len(payload_a["chapters"]) == 18
    assert len(payload_b["chapters"]) == 8


def test_adapter_can_include_appendix_when_enabled() -> None:
    springboot_path = _first_epub("springboot_in_action")

    payload_default = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )
    payload_with_appendix = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
        include_appendix=True,
    )

    assert len(payload_default["chapters"]) == 8
    assert len(payload_with_appendix["chapters"]) == 12


def test_adapter_type_c_distributes_sections_across_chapters() -> None:
    springboot_path = _first_epub("springboot_in_action")
    payload = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )

    chapters = payload["chapters"]
    section_counts: list[int] = []
    for chapter in chapters:
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        section_counts.append(len(sections))

    assert len(chapters) == 8
    assert all(count > 0 for count in section_counts)
    assert section_counts[-1] <= 10


def test_adapter_springboot_ch6_s3_keeps_numbered_bullets_aligned() -> None:
    springboot_path = _first_epub("springboot_in_action")
    payload = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )

    target_bullets: list[dict[str, object]] = []
    for chapter in payload["chapters"]:
        if chapter.get("id") != "springboot-in-action::ch6":
            continue
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if section.get("section_id") != "springboot-in-action::ch6::s3":
                continue
            bullets_obj = section.get("bullets")
            target_bullets = [b for b in bullets_obj if isinstance(b, dict)] if isinstance(
                bullets_obj, list
            ) else []
            break

    assert len(target_bullets) >= 4
    assert target_bullets[0]["text_raw"] == "6.3.1 Creating a new Grails project"
    assert target_bullets[1]["text_raw"] == "6.3.2 Defining the domain"
    assert target_bullets[1]["bullet_id"] == "springboot-in-action::ch6::s3::b2"


def test_adapter_springboot_drops_unnumbered_bullets_when_section_is_numbered() -> None:
    springboot_path = _first_epub("springboot_in_action")
    payload = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )

    numbered_bullet_re = re.compile(r"^\d+\.\d+\.\d+\b")
    for chapter in payload["chapters"]:
        chapter_id_obj = chapter.get("id")
        if not isinstance(chapter_id_obj, str):
            continue
        chapter_num = int(chapter_id_obj.rsplit("::ch", 1)[1])
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_id_obj = section.get("section_id")
            if not isinstance(section_id_obj, str):
                continue
            section_num = int(section_id_obj.rsplit("::s", 1)[1])
            bullets_obj = section.get("bullets")
            bullets = [b for b in bullets_obj if isinstance(b, dict)] if isinstance(
                bullets_obj, list
            ) else []
            if not bullets:
                continue
            has_numbered = any(
                isinstance(b.get("text_raw"), str)
                and numbered_bullet_re.match(b.get("text_raw", "")) is not None
                for b in bullets
            )
            if not has_numbered:
                continue
            for bullet in bullets:
                text_raw_obj = bullet.get("text_raw")
                assert isinstance(text_raw_obj, str)
                match = numbered_bullet_re.match(text_raw_obj)
                assert match is not None
                parts = text_raw_obj.split(" ", 1)[0].split(".")
                assert int(parts[0]) == chapter_num
                assert int(parts[1]) == section_num


def test_adapter_springboot_numeric_section_titles_align_with_section_ids() -> None:
    springboot_path = _first_epub("springboot_in_action")
    payload = build_adapter_payload(
        epub_path=springboot_path,
        book_id="springboot-in-action",
    )

    for chapter in payload["chapters"]:
        chapter_id_obj = chapter.get("id")
        if not isinstance(chapter_id_obj, str):
            continue
        chapter_num = int(chapter_id_obj.rsplit("::ch", 1)[1])
        sections_obj = chapter.get("sections")
        sections = sections_obj if isinstance(sections_obj, list) else []
        for section in sections:
            if not isinstance(section, dict):
                continue
            title_raw_obj = section.get("title_raw")
            if not isinstance(title_raw_obj, str):
                continue
            match = re.match(r"^\s*(\d+)\.(\d+)\b", title_raw_obj)
            if match is None:
                continue
            section_id_obj = section.get("section_id")
            assert isinstance(section_id_obj, str)
            section_num = int(section_id_obj.rsplit("::s", 1)[1])
            assert int(match.group(1)) == chapter_num
            assert int(match.group(2)) == section_num
