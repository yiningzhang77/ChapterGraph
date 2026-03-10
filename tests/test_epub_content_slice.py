from pathlib import Path

import pytest

from feature_achievement.epub.content import extract_anchor_slice_from_epub


def _first_epub(folder: str) -> Path:
    root = Path("book_epub") / folder
    if not root.exists():
        pytest.skip(f"missing sample folder: {root}")
    candidates = sorted(root.glob("*.epub"))
    if not candidates:
        pytest.skip(f"missing sample epub in: {root}")
    return candidates[0]


def test_extract_anchor_slice_type_a_pnn_range() -> None:
    epub_path = _first_epub("spring_in_action")
    slice_data = extract_anchor_slice_from_epub(
        epub_path=epub_path,
        file_path="index_split_006.html",
        start_anchor="p416",
        end_anchor="p417",
    )
    assert slice_data is not None
    assert "Introducing Actuator" in slice_data.text
    assert slice_data.start_offset < slice_data.end_offset


def test_extract_anchor_slice_type_b_sigil_range() -> None:
    epub_path = _first_epub("spring_start_here")
    slice_data = extract_anchor_slice_from_epub(
        epub_path=epub_path,
        file_path="OEBPS/ch01.htm",
        start_anchor="sigil_toc_id_13",
        end_anchor="sigil_toc_id_14",
    )
    assert slice_data is not None
    assert "Discovering Spring Core" in slice_data.text
    assert slice_data.start_offset < slice_data.end_offset


def test_extract_anchor_slice_type_c_heading_range() -> None:
    epub_path = _first_epub("springboot_in_action")
    slice_data = extract_anchor_slice_from_epub(
        epub_path=epub_path,
        file_path="OEBPS/Text/07.html",
        start_anchor="heading_id_3",
        end_anchor="heading_id_4",
    )
    assert slice_data is not None
    assert "Exploring the Actuator" in slice_data.text
    assert slice_data.start_offset < slice_data.end_offset
