from pathlib import Path

import pytest

from feature_achievement.epub.source_refs import (
    SOURCE_REF_FORMAT,
    build_source_refs_for_range_from_epub,
    build_source_refs_with_fallback_from_epub,
    validate_source_ref_schema,
)


def _first_epub(folder: str) -> Path:
    root = Path("book_epub") / folder
    if not root.exists():
        pytest.skip(f"missing sample folder: {root}")
    candidates = sorted(root.glob("*.epub"))
    if not candidates:
        pytest.skip(f"missing sample epub in: {root}")
    return candidates[0]


def test_build_source_refs_for_range_generates_schema_valid_ref() -> None:
    epub_path = _first_epub("spring_start_here")
    refs = build_source_refs_for_range_from_epub(
        epub_path=epub_path,
        file_path="OEBPS/ch01.htm",
        start_anchor="sigil_toc_id_13",
        end_anchor="sigil_toc_id_14",
    )

    assert refs is not None
    assert len(refs) == 1
    ref = refs[0]
    assert ref["format"] == SOURCE_REF_FORMAT
    assert validate_source_ref_schema(ref)
    assert "Discovering Spring Core" in ref["snippet"]


def test_build_source_refs_falls_back_to_section_when_bullet_anchor_missing() -> None:
    epub_path = _first_epub("springboot_in_action")
    refs, mode = build_source_refs_with_fallback_from_epub(
        epub_path=epub_path,
        file_path="OEBPS/Text/07.html",
        bullet_start_anchor="missing_bullet_anchor",
        bullet_end_anchor=None,
        section_start_anchor="heading_id_3",
        section_end_anchor="heading_id_4",
    )

    assert mode == "section_fallback"
    assert refs is not None
    assert refs[0]["origin"] == "section_fallback"
    assert refs[0]["confidence"] == 0.72


def test_build_source_refs_reports_unresolved_when_no_anchor_can_map() -> None:
    epub_path = _first_epub("springboot_in_action")
    refs, mode = build_source_refs_with_fallback_from_epub(
        epub_path=epub_path,
        file_path="OEBPS/Text/07.html",
        bullet_start_anchor="missing_bullet_anchor",
        bullet_end_anchor=None,
        section_start_anchor=None,
        section_end_anchor=None,
    )

    assert mode == "unresolved"
    assert refs is None
