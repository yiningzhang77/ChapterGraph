from pathlib import Path

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
