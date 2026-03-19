2026-03-19 20:11

# Goal + Plan Schema Commit List

This commit list implements [goal-plan-schema-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/study-agent-subplans-03192008/goal-plan-schema-plan.md).

Scope:

- define the typed nouns for the study agent
- keep this contract-first
- do not implement planner behavior yet
- do not introduce persistence yet

## Commit 01

`feat(study-agent): add goal schema contracts`

Status: `completed`

### Scope

Add the first normalized goal vocabulary, for example in:

- `feature_achievement/study_agent/goal_contracts.py`

### Changes

- add `LearningGoal`
- add goal-related enums / literals as needed
- add explicit fields for:
  - primary topics
  - background topics
  - desired depth
  - optional constraints

### Constraint

Do not add planning logic yet.

## Commit 02

`feat(study-agent): add plan schema contracts`

Status: `completed`

### Scope

Add typed plan vocabulary, for example in:

- `feature_achievement/study_agent/plan_contracts.py`

### Changes

- add `StudyPlan`
- add `PlanStage`
- add `PlanItem`
- add item status enum / literal
- add stable ids for plan, stage, and item

### Goal

A planner should later be able to return a typed plan without inventing ad hoc dicts.

## Commit 03

`feat(study-agent): add plan change schema contracts`

Status: `completed`

### Scope

Define the diff vocabulary for future replanning.

### Changes

- add `PlanChange`
- add optional change item records such as:
  - inserted items
  - removed items
  - reordered items
- add explicit `reason` / `change_source`

### Constraint

Do not implement replanning behavior yet.

## Commit 04

`feat(study-agent): add sample fixtures for goal and plan schemas`

Status: `completed`

### Scope

Add a few realistic examples that match the current study-agent direction.

### Suggested files

- `tests/fixtures/learning_goal_examples.py`
- `tests/fixtures/study_plan_examples.py`

### Changes

- add at least one beginner Spring goal
- add at least one focused topic goal
- add at least one multi-stage study plan example

### Goal

Make later planner/progress work validate against realistic shapes.

## Commit 05

`test(study-agent): add focused schema coverage for goal and plan contracts`

Status: `completed`

### Scope

Verify normalization and structural guarantees.

### Changes

- test goal creation
- test plan creation
- test plan item status handling
- test plan change structure
- test fixture validity

### Suggested files

- `tests/test_goal_contracts.py`
- `tests/test_plan_contracts.py`

## Commit 06

`docs(study-agent): record goal and plan schema completion`

Status: `completed`

### Scope

Update the plan doc once the schema layer is real.

### Changes

- mark contract layer progress in:
  - [goal-plan-schema-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/study-agent-subplans-03192008/goal-plan-schema-plan.md)
- optionally add brief notes on:
  - what was deferred
  - what the planner can now rely on

## Recommended Order

1. goal schema
2. plan schema
3. plan change schema
4. fixtures
5. focused tests
6. doc update

## Stop Conditions

Stop and reassess if:

- planner heuristics start appearing in schema files
- persistence concerns leak into contracts
- contracts become tailored to one single book set instead of stable study-agent nouns

## Bottom Line

This step is complete when:

- `LearningGoal`, `StudyPlan`, `PlanStage`, `PlanItem`, and `PlanChange` exist as typed contracts
- realistic fixtures exist
- tests prove the schema layer is stable enough for planner MVP work
