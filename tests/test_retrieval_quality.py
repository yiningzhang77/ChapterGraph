from feature_achievement.ask.retrieval_quality import (
    broad_overview_prompt_note,
    default_term_user_query,
    evaluate_term_retrieval_quality,
)


def _cluster(
    seed_ids: list[str], chapters: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": "cluster.v1",
        "query": "What is Spring?",
        "query_type": "term",
        "run_id": 1,
        "enrichment_version": "v2_indexed_sections_bullets",
        "seed": {
            "seed_chapter_ids": seed_ids,
            "seed_reason": "term_ilike",
        },
        "chapters": chapters,
        "edges": [],
        "constraints": {},
    }


def _chapters(chapter_count: int, book_count: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(chapter_count):
        rows.append(
            {
                "chapter_id": f"book{index % book_count}::ch{index + 1}",
                "book_id": f"book{index % book_count}",
                "title": f"Chapter {index + 1}",
                "chapter_text": "",
                "chapter_index_text": "",
            }
        )
    return rows


def _evidence(chapter_ids: list[str]) -> dict[str, object]:
    return {
        "sections": [],
        "bullets": [
            {
                "chapter_id": chapter_id,
                "section_id": f"{chapter_id}::s1",
                "bullet_id": f"{chapter_id}::s1::b1",
                "text_norm": "text",
                "text_raw": "text",
                "score": 1.0,
                "source_refs": None,
            }
            for chapter_id in chapter_ids
        ],
    }


def test_evaluate_term_retrieval_quality_returns_none_for_clean_retrieval() -> None:
    cluster = _cluster(
        seed_ids=["book0::ch1", "book0::ch2"],
        chapters=_chapters(2),
    )
    quality = evaluate_term_retrieval_quality(
        term="Actuator",
        user_query="Tell me about Actuator",
        user_query_was_default=False,
        cluster=cluster,
        evidence=_evidence(["book0::ch1", "book0::ch2"]),
    )
    assert quality is None


def test_evaluate_term_retrieval_quality_blocks_precise_broad_query() -> None:
    chapters = _chapters(6, book_count=3)
    cluster = _cluster(
        seed_ids=[row["chapter_id"] for row in chapters[:5]],
        chapters=chapters,
    )
    quality = evaluate_term_retrieval_quality(
        term="Spring",
        user_query="How does Spring implement data persistence?",
        user_query_was_default=False,
        cluster=cluster,
        evidence=_evidence([row["chapter_id"] for row in chapters[:6]]),
    )

    assert quality is not None
    assert quality["state"] == "broad_blocked"
    assert quality["term_too_broad"] is True
    assert quality["evidence_too_scattered"] is True
    assert quality["suggested_terms"] == [
        "Spring Boot",
        "Spring MVC",
        "Spring Data",
        "Spring Security",
    ]


def test_evaluate_term_retrieval_quality_allows_definition_broad_query() -> None:
    chapters = _chapters(5, book_count=2)
    cluster = _cluster(
        seed_ids=[row["chapter_id"] for row in chapters[:5]],
        chapters=chapters,
    )
    quality = evaluate_term_retrieval_quality(
        term="Spring",
        user_query="What is Spring?",
        user_query_was_default=False,
        cluster=cluster,
        evidence=_evidence([row["chapter_id"] for row in chapters[:5]]),
    )

    assert quality is not None
    assert quality["state"] == "broad_allowed"
    assert quality["message"] == (
        "This term is broad, so the answer is limited to a high-level overview."
    )


def test_evaluate_term_retrieval_quality_blocks_default_query_for_broad_term() -> None:
    chapters = _chapters(5, book_count=2)
    cluster = _cluster(
        seed_ids=[row["chapter_id"] for row in chapters[:5]],
        chapters=chapters,
    )
    default_query = default_term_user_query("Spring")
    quality = evaluate_term_retrieval_quality(
        term="Spring",
        user_query=default_query,
        user_query_was_default=True,
        cluster=cluster,
        evidence=_evidence([row["chapter_id"] for row in chapters[:5]]),
    )

    assert quality is not None
    assert quality["state"] == "broad_blocked"


def test_broad_overview_prompt_note_mentions_suggested_terms() -> None:
    note = broad_overview_prompt_note(["Spring Boot", "Spring Data"])
    assert "high-level concept explanation" in note
    assert "Spring Boot, Spring Data" in note
