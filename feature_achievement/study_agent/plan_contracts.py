from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

PlanItemStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "skipped",
    "blocked",
]


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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


class PlanItem(BaseModel):
    item_id: str
    book_id: str
    chapter_id: str
    order: int = Field(ge=1)
    why: str
    status: PlanItemStatus = "pending"
    prerequisite_item_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize(self) -> "PlanItem":
        self.item_id = _normalize_text(self.item_id) or ""
        self.book_id = _normalize_text(self.book_id) or ""
        self.chapter_id = _normalize_text(self.chapter_id) or ""
        self.why = _normalize_text(self.why) or ""
        self.prerequisite_item_ids = _normalize_text_list(self.prerequisite_item_ids)
        if not self.item_id:
            raise ValueError("item_id is required")
        if not self.book_id:
            raise ValueError("book_id is required")
        if not self.chapter_id:
            raise ValueError("chapter_id is required")
        if not self.why:
            raise ValueError("why is required")
        return self


class PlanStage(BaseModel):
    stage_id: str
    title: str
    order: int = Field(ge=1)
    items: list[PlanItem] = Field(min_length=1)

    @model_validator(mode="after")
    def normalize(self) -> "PlanStage":
        self.stage_id = _normalize_text(self.stage_id) or ""
        self.title = _normalize_text(self.title) or ""
        if not self.stage_id:
            raise ValueError("stage_id is required")
        if not self.title:
            raise ValueError("title is required")

        seen_item_ids: set[str] = set()
        for item in self.items:
            if item.item_id in seen_item_ids:
                raise ValueError(f"duplicate item_id in stage: {item.item_id}")
            seen_item_ids.add(item.item_id)
        return self


class StudyPlan(BaseModel):
    plan_id: str
    goal_summary: str
    stages: list[PlanStage] = Field(min_length=1)
    next_recommended_item_id: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "StudyPlan":
        self.plan_id = _normalize_text(self.plan_id) or ""
        self.goal_summary = _normalize_text(self.goal_summary) or ""
        self.next_recommended_item_id = _normalize_text(self.next_recommended_item_id)

        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not self.goal_summary:
            raise ValueError("goal_summary is required")

        seen_stage_ids: set[str] = set()
        all_item_ids: set[str] = set()
        for stage in self.stages:
            if stage.stage_id in seen_stage_ids:
                raise ValueError(f"duplicate stage_id in plan: {stage.stage_id}")
            seen_stage_ids.add(stage.stage_id)
            for item in stage.items:
                if item.item_id in all_item_ids:
                    raise ValueError(f"duplicate item_id in plan: {item.item_id}")
                all_item_ids.add(item.item_id)

        if self.next_recommended_item_id and self.next_recommended_item_id not in all_item_ids:
            raise ValueError("next_recommended_item_id must reference an existing item")
        return self
