from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AskRequest(BaseModel):
    query: str | None = None
    term: str | None = None
    user_query: str | None = None
    query_type: Literal["term", "chapter"] = "term"
    run_id: int
    enrichment_version: str = "v2_indexed_sections_bullets"
    chapter_id: str | None = None
    max_hops: int = Field(2, ge=0, le=2)
    seed_top_k: int = Field(5, ge=1, le=50)
    neighbor_top_k: int = Field(40, ge=1, le=200)
    section_top_k: int = Field(10, ge=1, le=100)
    bullet_top_k: int = Field(20, ge=1, le=200)
    min_edge_score: float = Field(0.2, ge=0.0, le=1.0)
    llm_enabled: bool = True
    llm_model: str = "qwen"
    llm_timeout_ms: int = Field(60000, ge=1000, le=120000)
    return_cluster: bool = True
    return_graph_fragment: bool = True

    @model_validator(mode="after")
    def normalize(self):
        if self.query is not None:
            self.query = self.query.strip()
            if not self.query:
                self.query = None
        if self.term is not None:
            self.term = self.term.strip()
            if not self.term:
                self.term = None
        if self.user_query is not None:
            self.user_query = self.user_query.strip()
            if not self.user_query:
                self.user_query = None
        if self.chapter_id is not None:
            self.chapter_id = self.chapter_id.strip()
            if not self.chapter_id:
                self.chapter_id = None

        if self.query_type == "term":
            if not self.term:
                raise ValueError("term is required for term query_type")
            if not self.user_query:
                self.user_query = (
                    f'Explain the term "{self.term}" using the retrieved cluster.'
                )
            self.query = self.user_query
        else:
            if not self.chapter_id:
                raise ValueError("chapter_id is required for chapter query_type")
            if not self.query:
                self.query = (
                    f'Summarize the selected chapter "{self.chapter_id}" '
                    "using the retrieved cluster."
                )
        return self


class AskResponse(BaseModel):
    query: str
    query_type: str
    run_id: int
    enrichment_version: str
    answer_markdown: str | None = None
    cluster: dict[str, object] | None = None
    evidence: dict[str, object] | None = None
    graph_fragment: dict[str, object] | None = None
    meta: dict[str, object] = Field(default_factory=dict)
