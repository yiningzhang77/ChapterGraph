2026-03-19 20:08

# Goal + Plan Schema Plan

Status: `completed`

## Purpose

Define the core data contracts for the study agent before implementing planner behavior.

This subplan owns:

- `LearningGoal`
- `StudyPlan`
- `PlanStage`
- `PlanItem`
- `PlanChange`

## Why This Comes First

The planner, progress tracker, and replanner all depend on the same stable nouns.

Without explicit schemas, later flows will drift into ad hoc dictionaries.

## Scope

### In

- typed schema classes
- normalization rules
- state enums for plan items
- plan update / diff shape

### Out

- actual planning logic
- persistence layer
- UI rendering

## Required Contracts

### LearningGoal

Should normalize:

- primary topics
- background / prerequisites
- desired depth
- optional constraints

### StudyPlan

Should contain:

- plan id
- goal summary
- stages
- items within stages
- next recommended item

### PlanItem

Should minimally include:

- `book_id`
- `chapter_id`
- `order`
- `why`
- `status`

### PlanChange

Should describe:

- inserted items
- removed items
- reordered items
- reason for change

## Suggested Output

This subplan should end with:

- a typed schema module
- focused schema tests
- a few sample fixtures

Delivered:

- `feature_achievement/study_agent/goal_contracts.py`
- `feature_achievement/study_agent/plan_contracts.py`
- `feature_achievement/study_agent/plan_change_contracts.py`
- `tests/fixtures/learning_goal_examples.py`
- `tests/fixtures/study_plan_examples.py`
- `tests/test_goal_contracts.py`
- `tests/test_plan_contracts.py`

What was intentionally deferred:

- planner behavior
- persistence
- plan storage
- user progress state

## Done When

- planner inputs/outputs no longer depend on loose dicts
- progress tracker can reference plan items by stable ids
- replanner can produce an explicit plan diff

Validation:

```powershell
python -m pytest -q tests/test_goal_contracts.py tests/test_plan_contracts.py
```

Latest result:

- `8 passed`
