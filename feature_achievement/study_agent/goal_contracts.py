from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

GoalType = Literal[
    "learn_topic",
    "build_roadmap",
    "review_topic",
]

LearningDepth = Literal[
    "overview",
    "practical",
    "deep",
]


def _normalize_text_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        key = stripped.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(stripped)
    return normalized


class GoalConstraints(BaseModel):
    time_budget_hours: int | None = Field(default=None, ge=1)
    exclude_topics: list[str] = Field(default_factory=list)
    preferred_books: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize(self) -> "GoalConstraints":
        self.exclude_topics = _normalize_text_list(self.exclude_topics)
        self.preferred_books = _normalize_text_list(self.preferred_books)
        return self


class LearningGoal(BaseModel):
    goal_type: GoalType = "learn_topic"
    primary_topics: list[str] = Field(min_length=1)
    background_topics: list[str] = Field(default_factory=list)
    desired_depth: LearningDepth = "practical"
    constraints: GoalConstraints = Field(default_factory=GoalConstraints)
    goal_summary: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "LearningGoal":
        self.primary_topics = _normalize_text_list(self.primary_topics)
        self.background_topics = _normalize_text_list(self.background_topics)
        if self.goal_summary is not None:
            stripped = self.goal_summary.strip()
            self.goal_summary = stripped or None
        if not self.primary_topics:
            raise ValueError("primary_topics must contain at least one non-empty topic")
        return self
