from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from feature_achievement.db.engine import engine

router = APIRouter(prefix="", tags=["health"])


def check_database_ready() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        check_database_ready()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database not ready") from exc
    return {"status": "ready"}
