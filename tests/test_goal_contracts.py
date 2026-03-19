import pytest
from pydantic import ValidationError

from feature_achievement.study_agent.goal_contracts import GoalConstraints, LearningGoal
from tests.fixtures.learning_goal_examples import (
    BEGINNER_SPRING_BOOT_GOAL,
    SPRING_PERSISTENCE_GOAL,
)


def test_learning_goal_normalizes_topics_and_summary() -> None:
    goal = LearningGoal(
        primary_topics=[" Spring Boot ", "spring boot", "Data Persistence"],
        background_topics=[" Java ", "", "java"],
        constraints=GoalConstraints(exclude_topics=[" reactive ", "Reactive"]),
        goal_summary="  Learn Spring app development  ",
    )

    assert goal.primary_topics == ["Spring Boot", "Data Persistence"]
    assert goal.background_topics == ["Java"]
    assert goal.constraints.exclude_topics == ["reactive"]
    assert goal.goal_summary == "Learn Spring app development"


def test_learning_goal_requires_non_empty_primary_topics() -> None:
    with pytest.raises(ValidationError):
        LearningGoal(primary_topics=[" ", ""])


def test_learning_goal_fixtures_are_valid() -> None:
    assert BEGINNER_SPRING_BOOT_GOAL.primary_topics == [
        "Spring Boot",
        "Spring fundamentals",
    ]
    assert SPRING_PERSISTENCE_GOAL.desired_depth == "deep"
    assert SPRING_PERSISTENCE_GOAL.constraints.preferred_books == [
        "spring-start-here",
        "spring-in-action",
    ]
