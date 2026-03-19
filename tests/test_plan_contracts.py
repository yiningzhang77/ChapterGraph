import pytest
from pydantic import ValidationError

from feature_achievement.study_agent.plan_change_contracts import (
    InsertedPlanItemChange,
    PlanChange,
)
from feature_achievement.study_agent.plan_contracts import (
    PlanItem,
    PlanStage,
    StudyPlan,
)
from tests.fixtures.study_plan_examples import MULTI_STAGE_SPRING_PLAN


def test_study_plan_validates_ids_and_next_item() -> None:
    plan = StudyPlan(
        plan_id=" plan-001 ",
        goal_summary=" Learn Spring Boot ",
        stages=[
            PlanStage(
                stage_id=" stage-1 ",
                title=" Foundations ",
                order=1,
                items=[
                    PlanItem(
                        item_id=" item-1 ",
                        book_id=" spring-start-here ",
                        chapter_id="spring-start-here::ch1",
                        order=1,
                        why=" Introduces Spring. ",
                    )
                ],
            )
        ],
        next_recommended_item_id=" item-1 ",
    )

    assert plan.plan_id == "plan-001"
    assert plan.stages[0].stage_id == "stage-1"
    assert plan.stages[0].items[0].item_id == "item-1"
    assert plan.next_recommended_item_id == "item-1"


def test_study_plan_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValidationError):
        StudyPlan(
            plan_id="plan-1",
            goal_summary="Goal",
            stages=[
                PlanStage(
                    stage_id="stage-1",
                    title="One",
                    order=1,
                    items=[
                        PlanItem(
                            item_id="item-1",
                            book_id="book-a",
                            chapter_id="book-a::ch1",
                            order=1,
                            why="First",
                        ),
                    ],
                ),
                PlanStage(
                    stage_id="stage-2",
                    title="Two",
                    order=2,
                    items=[
                        PlanItem(
                            item_id="item-1",
                            book_id="book-b",
                            chapter_id="book-b::ch2",
                            order=1,
                            why="Second",
                        ),
                    ],
                ),
            ],
        )


def test_plan_change_requires_real_modification() -> None:
    with pytest.raises(ValidationError):
        PlanChange(
            plan_id="plan-1",
            change_source="planner",
        )


def test_plan_change_accepts_inserted_item() -> None:
    change = PlanChange(
        plan_id="plan-1",
        change_source="prerequisite",
        inserted_items=[
            InsertedPlanItemChange(
                stage_id="stage-1",
                item=PlanItem(
                    item_id="item-2",
                    book_id="spring-start-here",
                    chapter_id="spring-start-here::ch2",
                    order=2,
                    why="Needed prerequisite",
                ),
                before_item_id="item-1",
            )
        ],
    )

    assert change.inserted_items[0].item.item_id == "item-2"


def test_study_plan_fixture_is_valid() -> None:
    assert MULTI_STAGE_SPRING_PLAN.plan_id == "plan-spring-boot-foundations"
    assert MULTI_STAGE_SPRING_PLAN.next_recommended_item_id == "item-ssh-ch1"
    assert len(MULTI_STAGE_SPRING_PLAN.stages) == 2
    assert MULTI_STAGE_SPRING_PLAN.stages[1].items[0].prerequisite_item_ids == [
        "item-ssh-ch1",
        "item-ssh-ch2",
    ]
