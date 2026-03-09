from feature_achievement.scripts.validate_enriched_v2 import validate_enriched_book


def _valid_book() -> dict[str, object]:
    return {
        "book_id": "spring-in-action",
        "chapters": [
            {
                "id": "spring-in-action::ch1",
                "title": "Getting started with Spring",
                "chapter_text": "book:spring in action chapter:spring in action ch1 bullet:none",
                "chapter_index_text": "book:spring in action chapter:spring in action ch1 bullet:none",
                "sections": [
                    {
                        "section_id": "spring-in-action::ch1::s1",
                        "order": 1,
                        "title_raw": "1.1 What is Spring?",
                        "title_norm": "what is spring",
                        "bullets": [
                            {
                                "bullet_id": "spring-in-action::ch1::s1::b1",
                                "order": 1,
                                "text_raw": "1.1.1 Handling web requests",
                                "text_norm": "handling web requests",
                                "source_refs": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_validate_enriched_v2_passes_for_valid_shape() -> None:
    errors = validate_enriched_book(_valid_book(), source_name="sample")
    assert errors == []


def test_validate_enriched_v2_fails_when_signals_or_legacy_sections_exist() -> None:
    broken = _valid_book()
    chapters = broken["chapters"]
    assert isinstance(chapters, list)
    chapter = chapters[0]
    assert isinstance(chapter, dict)
    chapter["signals"] = {"bullets": ["legacy"]}  # forbidden in v2
    chapter["sections"] = ["legacy-string-section"]  # forbidden in v2

    errors = validate_enriched_book(broken, source_name="broken")
    assert any("signals" in err for err in errors)
    assert any("section[1]: must be object" in err for err in errors)
