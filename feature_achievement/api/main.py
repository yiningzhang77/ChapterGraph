from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from feature_achievement.api.routers import ask, edges
from feature_achievement.runtime_config import get_cors_origins

app = FastAPI(title="ChapterGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(edges.router)
app.include_router(ask.router)
