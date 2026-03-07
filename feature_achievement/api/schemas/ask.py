from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    run_id: int
    enrichment_version: str = "v1_bullets+sections"


class AskResponse(BaseModel):
    query: str
    run_id: int
    enrichment_version: str
    message: str

