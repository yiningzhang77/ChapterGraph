from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    query_type: Literal["term", "chapter"] = "term"
    run_id: int
    enrichment_version: str = "v1_bullets+sections"
    chapter_id: str | None = None
    max_hops: int = Field(2, ge=0, le=2)
    seed_top_k: int = Field(5, ge=1, le=50)
    neighbor_top_k: int = Field(40, ge=1, le=200)
    min_edge_score: float = Field(0.2, ge=0.0, le=1.0)
    return_cluster: bool = True
    return_graph_fragment: bool = True

    @model_validator(mode="after")
    def normalize(self):
        self.query = self.query.strip()
        if self.query_type == "chapter" and not self.chapter_id:
            self.chapter_id = self.query
        return self


class AskResponse(BaseModel):
    query: str
    query_type: str
    run_id: int
    enrichment_version: str
    cluster: dict[str, object] | None = None
    graph_fragment: dict[str, object] | None = None
    meta: dict[str, object] = Field(default_factory=dict)
