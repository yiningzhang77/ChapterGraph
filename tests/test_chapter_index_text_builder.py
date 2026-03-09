from feature_achievement.enrichment import enrich_chapter_text


def test_enrich_chapter_text_builds_index_text_and_removes_signals() -> None:
    data: dict[str, object] = {
        "book_id": "spring-in-action",
        "chapters": [
            {
                "id": "spring-in-action::ch1",
                "title": "Getting started with Spring",
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
                "signals": {"bullets": ["legacy"], "raw_text": ""},
            },
            {
                "id": "spring-in-action::ch2",
                "title": "Securing REST",
                "sections": [
                    {
                        "section_id": "spring-in-action::ch2::s1",
                        "order": 1,
                        "title_raw": "2.1 Introducing OAuth 2",
                        "title_norm": "introducing oauth 2",
                        "bullets": [],
                    }
                ],
            },
        ],
    }

    enriched = enrich_chapter_text(data)
    chapters = enriched["chapters"]
    assert isinstance(chapters, list)
    first = chapters[0]
    second = chapters[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)

    assert "signals" not in first
    first_index_text = first["chapter_index_text"]
    assert isinstance(first_index_text, str)
    assert "book:spring in action" in first_index_text
    assert "chapter:spring in action ch1" in first_index_text
    assert "section:what is spring" in first_index_text
    assert "bullet:handling web requests" in first_index_text
    assert first["chapter_text"] == first_index_text

    second_index_text = second["chapter_index_text"]
    assert isinstance(second_index_text, str)
    assert "bullet:none" in second_index_text
    assert second["chapter_text"] == second_index_text
