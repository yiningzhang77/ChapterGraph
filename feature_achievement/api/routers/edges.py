from dataclasses import dataclass
from datetime import datetime
import json
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from feature_achievement.api.deps import (
    RetrievalResources,
    get_retrieval_resources,
)
from feature_achievement.db.crud import persist_books_and_chapters, persist_edges
from feature_achievement.db.engine import get_session
from feature_achievement.db.models import Book, Chapter, Edge, Run
from feature_achievement.retrieval.candidates.base import CandidateGenerator
from feature_achievement.retrieval.candidates.tfidf_token import (
    TfidfTokenCandidateGenerator,
)
from feature_achievement.retrieval.edge_generation import generate_edges
from feature_achievement.retrieval.pipeline import RetrievalPipeline
from feature_achievement.retrieval.similarity.base import SimilarityScorer
from feature_achievement.retrieval.similarity.embedding import EmbeddingSimilarityScorer
from feature_achievement.retrieval.similarity.tfidf import TfidfSimilarityScorer
from feature_achievement.retrieval.utils.embedding import build_embedding_index
from feature_achievement.retrieval.utils.text import collect_chapter_texts
from feature_achievement.retrieval.utils.tfidf import (
    build_tfidf_index,
    build_token_index,
    extract_top_tfidf_tokens,
)

from .compute_edges_request import (
    CandidateGeneratorType,
    ComputeEdgesRequest,
    SimilarityType,
)

router = APIRouter(prefix="", tags=["edges"])


@dataclass
class RetrievalRuntime:
    enriched_books: list[dict]
    chapter_texts: dict[str, str]
    tfidf_index: dict[str, object]
    candidate_generator: CandidateGenerator
    similarity_scorer: SimilarityScorer
    pipeline: RetrievalPipeline


def select_similarity_scorer(
    req: ComputeEdgesRequest,
    chapter_texts: dict[str, str],
    tfidf_index: dict[str, object],
) -> SimilarityScorer:
    if req.similarity == SimilarityType.embedding:
        model_name = req.embedding_model
        if model_name is None:
            raise HTTPException(
                status_code=422,
                detail="embedding_model is required when similarity='embedding'",
            )
        embedding_index = build_embedding_index(chapter_texts, model_name=model_name)
        return EmbeddingSimilarityScorer(embedding_index)
    if req.similarity == SimilarityType.tfidf:
        return TfidfSimilarityScorer(tfidf_index)
    raise HTTPException(status_code=400, detail="Unsupported similarity")


def build_retrieval_runtime(
    enriched_books: list[dict],
    req: ComputeEdgesRequest,
) -> RetrievalRuntime:
    chapter_texts = collect_chapter_texts(enriched_books)
    tfidf_index = build_tfidf_index(chapter_texts)

    if req.candidate_generator != CandidateGeneratorType.tfidf_token:
        raise HTTPException(status_code=400, detail="Unsupported candidate_generator")

    chapter_top_tokens = extract_top_tfidf_tokens(tfidf_index, top_n=20)
    token_index = build_token_index(chapter_top_tokens)
    candidate_generator = TfidfTokenCandidateGenerator(
        chapter_top_tokens=chapter_top_tokens,
        token_index=token_index,
        min_shared_tokens=2,
    )

    similarity_scorer = select_similarity_scorer(
        req=req,
        chapter_texts=chapter_texts,
        tfidf_index=tfidf_index,
    )

    pipeline = RetrievalPipeline(
        candidate_generator=candidate_generator,
        similarity_scorer=similarity_scorer,
        min_score=req.min_score,
    )
    return RetrievalRuntime(
        enriched_books=enriched_books,
        chapter_texts=chapter_texts,
        tfidf_index=tfidf_index,
        candidate_generator=candidate_generator,
        similarity_scorer=similarity_scorer,
        pipeline=pipeline,
    )


class GraphNode(BaseModel):
    id: str
    type: Literal["book", "chapter"]
    size: Optional[int] = None
    book_id: Optional[str] = None
    title: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    score: float
    type: str


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class RunResponse(BaseModel):
    id: int
    book_ids: List[str]
    candidate_generator: str
    similarity: str
    created_at: datetime


@router.post("/compute-edges")
def compute_edges(
    req: ComputeEdgesRequest,
    session: Session = Depends(get_session),
    resources: RetrievalResources = Depends(get_retrieval_resources),
):
    run = Run(
        book_ids=json.dumps(req.book_ids),
        enrichment_version=req.enrichment_version,
        candidate_generator=req.candidate_generator.value,
        similarity=req.similarity.value,
        min_score=req.min_score,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    enriched_books = [
        book for book in resources.enriched_books if book["book_id"] in req.book_ids
    ]
    if not enriched_books:
        raise HTTPException(
            status_code=400,
            detail="No matching books for requested book_ids",
        )

    retrieval_runtime = build_retrieval_runtime(enriched_books, req)
    edges = generate_edges(enriched_books, retrieval_runtime.pipeline)

    persist_books_and_chapters(enriched_books, session)
    persist_edges(edges, run.id, session)

    return {
        "run_id": run.id,
        "count": len(edges),
        "message": "edges computed and stored successfully",
    }


@router.get("/edges")
def list_edges(
    book_id: str,
    session: Session = Depends(get_session),
):
    stmt = (
        select(Edge)
        .join(Chapter, Edge.from_chapter == Chapter.id)
        .where(Chapter.book_id == book_id)
    )

    edges = session.exec(stmt).all()
    return {
        "count": len(edges),
        "edges": edges,
    }


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    run_id: int,
    session: Session = Depends(get_session),
):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    book_ids = json.loads(run.book_ids)

    books = session.exec(select(Book).where(Book.id.in_(book_ids))).all()
    chapters = session.exec(select(Chapter).where(Chapter.book_id.in_(book_ids))).all()
    edges = session.exec(select(Edge).where(Edge.run_id == run_id)).all()

    frontend = {
        "nodes": [],
        "edges": [],
    }

    for book in books:
        frontend["nodes"].append(
            {
                "id": book.id,
                "type": "book",
                "size": book.size,
            }
        )

    for chapter in chapters:
        frontend["nodes"].append(
            {
                "id": chapter.id,
                "type": "chapter",
                "book_id": chapter.book_id,
                "title": chapter.title,
            }
        )

    for edge in edges:
        frontend["edges"].append(
            {
                "source": edge.from_chapter,
                "target": edge.to_chapter,
                "score": edge.score,
                "type": edge.type,
            }
        )
    return frontend


@router.get("/runs", response_model=List[RunResponse])
def list_runs(session: Session = Depends(get_session)):
    runs = session.exec(select(Run).order_by(Run.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "book_ids": json.loads(r.book_ids),
            "candidate_generator": r.candidate_generator,
            "similarity": r.similarity,
            "created_at": r.created_at,
        }
        for r in runs
    ]
