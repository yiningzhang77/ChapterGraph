from feature_achievement.scripts.apply_source_refs_manual_patch import (
    apply_manual_source_refs_patch,
)


def _sample_book() -> dict[str, object]:
    return {
        "book_id": "sample-book",
        "chapters": [
            {
                "id": "sample-book::ch1",
                "title": "Sample chapter",
                "sections": [
                    {
                        "section_id": "sample-book::ch1::s1",
                        "order": 1,
                        "title_raw": "1.1 Intro",
                        "title_norm": "intro",
                        "bullets": [
                            {
                                "bullet_id": "sample-book::ch1::s1::b1",
                                "order": 1,
                                "text_raw": "1.1.1 A",
                                "text_norm": "a",
                                "source_refs": None,
                            },
                            {
                                "bullet_id": "sample-book::ch1::s1::b2",
                                "order": 2,
                                "text_raw": "1.1.2 B",
                                "text_norm": "b",
                                "source_refs": [
                                    {
                                        "format": "epub_anchor_v1",
                                        "file": "a.html",
                                        "start_anchor": "x",
                                        "end_anchor": "y",
                                        "selector": {"type": "id_range", "start": "x", "end": "y"},
                                        "snippet": "existing",
                                        "confidence": 0.9,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_apply_manual_patch_only_fills_null_refs() -> None:
    book = _sample_book()
    patch_items = [
        {
            "chapter_id": "sample-book::ch1",
            "bullet_id": "sample-book::ch1::s1::b1",
            "source_refs": [
                {
                    "format": "epub_anchor_v1",
                    "file": "b.html",
                    "start_anchor": "s",
                    "end_anchor": "e",
                    "selector": {"type": "id_range", "start": "s", "end": "e"},
                    "snippet": "manual",
                    "confidence": 0.95,
                }
            ],
        },
        {
            "chapter_id": "sample-book::ch1",
            "bullet_id": "sample-book::ch1::s1::b2",
            "source_refs": [
                {
                    "format": "epub_anchor_v1",
                    "file": "b.html",
                    "start_anchor": "s2",
                    "end_anchor": "e2",
                    "selector": {"type": "id_range", "start": "s2", "end": "e2"},
                    "snippet": "manual2",
                    "confidence": 0.91,
                }
            ],
        },
    ]

    stats = apply_manual_source_refs_patch(book, patch_items)

    chapters = book["chapters"]
    assert isinstance(chapters, list)
    chapter = chapters[0]
    assert isinstance(chapter, dict)
    sections = chapter["sections"]
    assert isinstance(sections, list)
    section = sections[0]
    assert isinstance(section, dict)
    bullets = section["bullets"]
    assert isinstance(bullets, list)
    bullet1 = bullets[0]
    bullet2 = bullets[1]
    assert isinstance(bullet1, dict)
    assert isinstance(bullet2, dict)

    refs1 = bullet1.get("source_refs")
    refs2 = bullet2.get("source_refs")
    assert isinstance(refs1, list)
    assert refs1[0]["snippet"] == "manual"
    assert isinstance(refs2, list)
    assert refs2[0]["snippet"] == "existing"
    assert stats == {"patched": 1, "skipped_existing": 1, "missing": 0}


def test_apply_manual_patch_counts_missing_rows() -> None:
    book = _sample_book()
    patch_items = [
        {
            "chapter_id": "sample-book::chX",
            "bullet_id": "sample-book::chX::s1::b1",
            "source_refs": [
                {
                    "format": "epub_anchor_v1",
                    "file": "m.html",
                    "start_anchor": "a",
                    "end_anchor": "b",
                    "selector": {"type": "id_range", "start": "a", "end": "b"},
                    "snippet": "missing",
                    "confidence": 0.8,
                }
            ],
        }
    ]
    stats = apply_manual_source_refs_patch(book, patch_items)
    assert stats == {"patched": 0, "skipped_existing": 0, "missing": 1}
