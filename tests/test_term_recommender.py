from feature_achievement.ask.term_recommender import recommend_narrower_terms


def test_recommend_narrower_terms_returns_persistence_suggestions() -> None:
    result = recommend_narrower_terms(
        broad_term="Spring",
        user_query="How does Spring implement data persistence?",
    )

    assert result["reason"] == "spring_persistence"
    assert result["suggested_terms"] == [
        "Spring Data",
        "data persistence",
        "JdbcTemplate",
        "Spring Data JPA",
    ]
    assert result["source"] == "rule_based"
    assert result["confidence"] == "heuristic"


def test_recommend_narrower_terms_returns_web_suggestions() -> None:
    result = recommend_narrower_terms(
        broad_term="Spring",
        user_query="How do controllers work in Spring MVC requests?",
    )

    assert result["reason"] == "spring_web"
    assert result["suggested_terms"] == [
        "Spring MVC",
        "controller",
        "request mapping",
    ]


def test_recommend_narrower_terms_returns_security_suggestions() -> None:
    result = recommend_narrower_terms(
        broad_term="Spring",
        user_query="How is authentication handled in Spring security?",
    )

    assert result["reason"] == "spring_security"
    assert result["suggested_terms"] == [
        "Spring Security",
        "authentication",
        "authorization",
    ]


def test_recommend_narrower_terms_returns_fallback_for_unmatched_term() -> None:
    result = recommend_narrower_terms(
        broad_term="Framework",
        user_query="How is dependency injection implemented?",
    )

    assert result["reason"] == "framework_fallback"
    assert result["suggested_terms"] == [
        "Actuator",
        "JdbcTemplate",
        "data persistence",
        "Spring Security",
    ]


def test_recommend_narrower_terms_returns_fallback_for_unmatched_query() -> None:
    result = recommend_narrower_terms(
        broad_term="Spring",
        user_query="Explain the ecosystem at a high level.",
    )

    assert result["reason"] == "spring_fallback"
    assert result["suggested_terms"] == [
        "Actuator",
        "JdbcTemplate",
        "data persistence",
        "Spring Security",
    ]
