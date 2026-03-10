from pathlib import Path

import pytest

from feature_achievement.epub.probe import probe_epub


def _first_epub(folder: str) -> Path:
    root = Path("book_epub") / folder
    if not root.exists():
        pytest.skip(f"missing sample folder: {root}")
    candidates = sorted(root.glob("*.epub"))
    if not candidates:
        pytest.skip(f"missing sample epub in: {root}")
    return candidates[0]


def test_probe_detects_type_a_split_pages() -> None:
    path = _first_epub("spring_in_action")
    result = probe_epub(path)
    assert result.content_layout_type == "type_a_split_pages"
    assert result.selected_strategy == "strategy_type_a_split_pages"
    assert result.confidence >= 0.6


def test_probe_detects_type_b_chapter_files() -> None:
    path = _first_epub("spring_start_here")
    result = probe_epub(path)
    assert result.content_layout_type == "type_b_chapter_files"
    assert result.selected_strategy == "strategy_type_b_chapter_files"
    assert result.confidence >= 0.6


def test_probe_detects_type_c_text_dir_chapters() -> None:
    path = _first_epub("springboot_in_action")
    result = probe_epub(path)
    assert result.content_layout_type == "type_c_text_dir_chapters"
    assert result.selected_strategy == "strategy_type_c_text_dir_chapters"
    assert result.confidence >= 0.6
