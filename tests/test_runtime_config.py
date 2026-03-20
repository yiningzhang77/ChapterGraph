from feature_achievement.runtime_config import (
    DEFAULT_CORS_ORIGINS,
    DEFAULT_DATABASE_URL,
    get_cors_origins,
    get_database_url,
)


def test_get_database_url_uses_default_when_env_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_database_url() == DEFAULT_DATABASE_URL


def test_get_database_url_prefers_env_value(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://app:secret@db:5432/chaptergraph",
    )

    assert (
        get_database_url()
        == "postgresql+psycopg2://app:secret@db:5432/chaptergraph"
    )


def test_get_cors_origins_uses_default_when_env_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert get_cors_origins() == DEFAULT_CORS_ORIGINS


def test_get_cors_origins_splits_comma_separated_values(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://app.example.com, https://staging.example.com ",
    )

    assert get_cors_origins() == [
        "https://app.example.com",
        "https://staging.example.com",
    ]
