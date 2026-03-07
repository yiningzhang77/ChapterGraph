from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from feature_achievement.api.schemas.ask import AskRequest, AskResponse
from feature_achievement.db.engine import get_session
from feature_achievement.db.models import Run

router = APIRouter(prefix="", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    session: Session = Depends(get_session),
):
    run = session.get(Run, req.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.enrichment_version != req.enrichment_version:
        raise HTTPException(
            status_code=409,
            detail=(
                "run.enrichment_version does not match request enrichment_version: "
                f"{run.enrichment_version} != {req.enrichment_version}"
            ),
        )

    return AskResponse(
        query=req.query,
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        message="ask api shell ready",
    )

