import os
from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql+psycopg2://postgres:1234@localhost:5432/chaptergraph"
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
APP_CONFIG_PATH = Path("config/app.env")


def _load_local_env_config() -> None:
    if not APP_CONFIG_PATH.exists():
        return

    for raw_line in APP_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def get_database_url() -> str:
    _load_local_env_config()
    value = os.getenv("DATABASE_URL", "").strip()
    return value or DEFAULT_DATABASE_URL


def get_cors_origins() -> list[str]:
    _load_local_env_config()
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if origins:
        return origins
    return list(DEFAULT_CORS_ORIGINS)
