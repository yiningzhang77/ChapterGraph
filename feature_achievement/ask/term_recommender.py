from __future__ import annotations

from collections.abc import Iterable


FALLBACK_SUGGESTED_TERMS = [
    "Actuator",
    "JdbcTemplate",
    "data persistence",
    "Spring Security",
]

BROAD_TERM_RULES: dict[str, list[dict[str, object]]] = {
    "spring": [
        {
            "reason": "spring_persistence",
            "match_any": ["data", "persistence", "jdbc", "jpa", "repository"],
            "suggested_terms": [
                "Spring Data",
                "data persistence",
                "JdbcTemplate",
                "Spring Data JPA",
            ],
        },
        {
            "reason": "spring_web",
            "match_any": ["web", "mvc", "controller", "request"],
            "suggested_terms": [
                "Spring MVC",
                "controller",
                "request mapping",
            ],
        },
        {
            "reason": "spring_security",
            "match_any": ["security", "auth", "authentication", "authorization"],
            "suggested_terms": [
                "Spring Security",
                "authentication",
                "authorization",
            ],
        },
    ],
    "data": [
        {
            "reason": "data_access",
            "match_any": ["access", "persistence", "jdbc", "jpa", "repository"],
            "suggested_terms": [
                "data persistence",
                "JdbcTemplate",
                "Spring Data JPA",
                "data source",
            ],
        }
    ],
    "security": [
        {
            "reason": "security_authentication",
            "match_any": ["auth", "authentication", "authorization", "endpoint"],
            "suggested_terms": [
                "Spring Security",
                "authentication",
                "Actuator endpoint security",
            ],
        }
    ],
}


def recommend_narrower_terms(
    *,
    broad_term: str,
    user_query: str,
) -> dict[str, object]:
    normalized_term = _normalize_text(broad_term)
    normalized_query = _normalize_text(user_query)
    term_rules = BROAD_TERM_RULES.get(normalized_term)
    if term_rules is not None:
        for rule in term_rules:
            keywords = rule.get("match_any")
            suggestions = rule.get("suggested_terms")
            reason = rule.get("reason")
            if (
                isinstance(keywords, list)
                and _matches_any(normalized_query, keywords)
                and isinstance(suggestions, list)
                and isinstance(reason, str)
            ):
                return {
                    "reason": reason,
                    "suggested_terms": [
                        suggestion
                        for suggestion in suggestions
                        if isinstance(suggestion, str)
                    ],
                    "source": "rule_based",
                    "confidence": "heuristic",
                }

    fallback_reason = (
        f"{normalized_term}_fallback" if normalized_term else "generic_fallback"
    )
    return {
        "reason": fallback_reason,
        "suggested_terms": FALLBACK_SUGGESTED_TERMS,
        "source": "rule_based",
        "confidence": "heuristic",
    }


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _matches_any(normalized_query: str, keywords: Iterable[object]) -> bool:
    if not normalized_query:
        return False
    return any(
        isinstance(keyword, str) and keyword in normalized_query for keyword in keywords
    )
