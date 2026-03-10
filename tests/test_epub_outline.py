import re
from pathlib import Path

import pytest

from feature_achievement.epub.outline import extract_outline
from feature_achievement.epub.probe import probe_epub


def _first_epub(folder: str) -> Path:
    root = Path("book_epub") / folder
    if not root.exists():
        pytest.skip(f"missing sample folder: {root}")
    candidates = sorted(root.glob("*.epub"))
    if not candidates:
        pytest.skip(f"missing sample epub in: {root}")
    return candidates[0]


def _chapter_like_count(titles: list[str]) -> int:
    return sum(1 for title in titles if re.match(r"^\d+\b", title))


def test_outline_type_a_priority_parses_document_outline_depth() -> None:
    epub_path = _first_epub("spring_in_action")
    probe_result = probe_epub(epub_path)
    nodes = extract_outline(epub_path, probe_result)

    assert probe_result.content_layout_type == "type_a_split_pages"
    assert len(nodes) >= 200
    assert max(node.level for node in nodes) >= 3
    assert _chapter_like_count([node.title for node in nodes]) >= 15


def test_outline_type_b_priority_parses_ncx_depth() -> None:
    epub_path = _first_epub("spring_start_here")
    probe_result = probe_epub(epub_path)
    nodes = extract_outline(epub_path, probe_result)

    assert probe_result.content_layout_type == "type_b_chapter_files"
    assert len(nodes) >= 150
    assert max(node.level for node in nodes) >= 3
    assert _chapter_like_count([node.title for node in nodes]) >= 15


def test_outline_type_c_uses_body_heading_augmentation() -> None:
    epub_path = _first_epub("springboot_in_action")
    probe_result = probe_epub(epub_path)
    nodes = extract_outline(epub_path, probe_result)

    assert probe_result.content_layout_type == "type_c_text_dir_chapters"
    assert len(nodes) >= 30
    assert max(node.level for node in nodes) >= 2
    assert _chapter_like_count([node.title for node in nodes]) >= 8
