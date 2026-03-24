2026-03-24 13:29

# Topic Membership Filter Commit List

This commit list implements [topic-membership-filter-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/topic-membership-filter-plan.md).

Scope:

- refine raw topic candidates into cleaner topic descriptors
- keep the logic deterministic
- keep retrieval graph unchanged
- do not build Topic DAG yet

## Commit 01

`feat(topic-study): add topic membership filter contracts`

Status: `completed`

### Scope

Add the typed schema layer for topic membership filtering.

### Suggested files

- `feature_achievement/topic_study/membership_contracts.py`

### Changes

- add `TopicMemberRole`
- add `TopicMembershipDecision`
- add `RefinedTopicDescriptor`
- add `RefinedTopicCatalog`

### Constraint

Do not add filter behavior yet.

## Commit 02

`feat(topic-study): add representative chapter selection and membership scoring`

Status: `completed`

### Scope

Add the first deterministic filter behavior.

### Suggested files

- `feature_achievement/topic_study/membership_filter.py`

### Changes

- choose representative chapter
- score candidate members against representative chapter
- assign `core` / `peripheral` / `excluded`

### Goal

Turn raw topic candidates into refined topic nodes.

## Commit 03

`feat(topic-study): add broad-topic detection and refined catalog build`

Status: `completed`

### Scope

Finish the first refined topic pass.

### Changes

- add `broad_topic_flag`
- build `RefinedTopicCatalog` from Stage 1 `TopicCatalog`
- keep representative chapter and membership decisions inspectable

### Constraint

Do not add Topic DAG relations yet.

## Commit 04

`feat(topic-study): add real-db smoke script for topic membership filtering`

Status: `completed`

### Scope

Validate the new refinement layer against current real data.

### Suggested files

- `feature_achievement/scripts/smoke_topic_membership_filter.py`

### Changes

- load Stage 1 topic catalog
- build refined topic catalog
- print representative chapter
- print core/peripheral/excluded counts
- print broad-topic flags
- fail clearly if refined output is malformed

## Commit 05

`test(topic-study): add focused coverage for membership filtering heuristics`

Status: `completed`

### Scope

Add unit tests for the deterministic filter layer.

### Suggested files

- `tests/test_topic_membership_filter.py`

### Changes

- test representative selection
- test core/peripheral/excluded assignment
- test broad-topic flag behavior
- test refined catalog output shape

## Commit 06

`docs(topic-study): record topic membership filter completion`

Status: `completed`

### Scope

Update the plan docs once the filter layer is real.

### Changes

- update:
  - [topic-membership-filter-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/topic-membership-filter-plan.md)
- record validation notes
- state what is still deferred to Topic DAG

## Recommended Order

1. contracts
2. representative + membership scoring
3. refined catalog + broad-topic flag
4. smoke
5. focused tests
6. doc update

## Stop Conditions

Stop and reassess if:

- filtering becomes query-dependent like `/ask`
- filter logic starts depending on topic-to-topic relations
- broad-topic detection turns into opaque special-casing
- the filter destroys most useful cross-book topic groupings

## Bottom Line

This stage is complete when:

- Stage 1 raw topics can be converted into `RefinedTopicCatalog`
- each refined topic has membership decisions and a representative chapter
- broad-topic detection exists
- the refined topic layer is stable enough to feed Topic DAG construction
