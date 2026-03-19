from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from feature_achievement.study_agent.plan_contracts import PlanItem

PlanChangeSource = Literal[
    "manual",
    "goal_update",
    "hotspot",
    "prerequisite",
    "planner",
]


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class InsertedPlanItemChange(BaseModel):
    stage_id: str
    item: PlanItem
    before_item_id: str | None = None
    after_item_id: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "InsertedPlanItemChange":
        self.stage_id = _normalize_text(self.stage_id) or ""
        self.before_item_id = _normalize_text(self.before_item_id)
        self.after_item_id = _normalize_text(self.after_item_id)
        self.reason = _normalize_text(self.reason)
        if not self.stage_id:
            raise ValueError("stage_id is required")
        return self


class RemovedPlanItemChange(BaseModel):
    item_id: str
    reason: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "RemovedPlanItemChange":
        self.item_id = _normalize_text(self.item_id) or ""
        self.reason = _normalize_text(self.reason)
        if not self.item_id:
            raise ValueError("item_id is required")
        return self


class ReorderedPlanItemChange(BaseModel):
    item_id: str
    from_stage_id: str
    to_stage_id: str
    from_order: int = Field(ge=1)
    to_order: int = Field(ge=1)
    reason: str | None = None

    @model_validator(mode="after")
    def normalize(self) -> "ReorderedPlanItemChange":
        self.item_id = _normalize_text(self.item_id) or ""
        self.from_stage_id = _normalize_text(self.from_stage_id) or ""
        self.to_stage_id = _normalize_text(self.to_stage_id) or ""
        self.reason = _normalize_text(self.reason)
        if not self.item_id:
            raise ValueError("item_id is required")
        if not self.from_stage_id:
            raise ValueError("from_stage_id is required")
        if not self.to_stage_id:
            raise ValueError("to_stage_id is required")
        return self


class PlanChange(BaseModel):
    plan_id: str
    change_source: PlanChangeSource
    reason: str | None = None
    inserted_items: list[InsertedPlanItemChange] = Field(default_factory=list)
    removed_items: list[RemovedPlanItemChange] = Field(default_factory=list)
    reordered_items: list[ReorderedPlanItemChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize(self) -> "PlanChange":
        self.plan_id = _normalize_text(self.plan_id) or ""
        self.reason = _normalize_text(self.reason)
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not (
            self.inserted_items
            or self.removed_items
            or self.reordered_items
        ):
            raise ValueError("plan change must contain at least one modification")
        return self
