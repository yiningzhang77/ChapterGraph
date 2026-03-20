from fastapi.testclient import TestClient

from feature_achievement.api.main import app
from feature_achievement.api.routers import health as health_router


def test_root_returns_service_summary() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "ChapterGraph API",
        "status": "ok",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "healthz": "/healthz",
        "readyz": "/readyz",
    }


def test_healthz_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ready_when_database_check_passes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(health_router, "check_database_ready", lambda: None)

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_returns_503_when_database_check_fails(
    monkeypatch,
) -> None:
    def fail() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(health_router, "check_database_ready", fail)

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"] == "database not ready"
