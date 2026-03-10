from feature_achievement.epub.content import clean_extracted_text


def test_clean_extracted_text_removes_headers_page_numbers_and_duplicates() -> None:
    raw_html = """
    <p>CHAPTER 15</p>
    <p>390</p>
    <p>Introducing Actuator</p>
    <p>Introducing Actuator</p>
    <p>   </p>
    <div>Actuator endpoints are configurable.</div>
    """

    cleaned = clean_extracted_text(raw_html)
    lines = cleaned.splitlines()

    assert "CHAPTER 15" not in cleaned
    assert "390" not in cleaned
    assert lines[0] == "Introducing Actuator"
    assert lines[1] == "Actuator endpoints are configurable."
    assert len(lines) == 2
