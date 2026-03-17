2026-03-17 14:58

# Hit Highlight Phase 1 Commit List

This document turns Phase 1 of [hit-highlight-plan.md](C:/Users/hy/ChapterGraph/chatbot/hit-highlight-plan.md) into an implementation sequence.

Goal:

- highlight nodes hit by the latest `/ask`
- compute deterministic hit intensity from the current response only
- show useful hit details on hover
- keep the implementation frontend-local

Phase 1 is intentionally narrow.
It does not include session accumulation or persistent memory.

## Commit 01

### `feat(frontend): build current-response ask hit map`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

### Changes

Add a frontend helper that derives a hit map from the latest `/ask` result.

Suggested helper boundary:

```javascript
function buildAskHitMap(result) {
  ...
}
```

The map should be keyed by `chapter_id` and include at least:

- `currentHitScore`
- `isSeed`
- `isClusterNode`
- `evidenceSectionCount`
- `evidenceBulletCount`
- `queryType`
- `queryLabel`

Suggested deterministic scoring:

- seed hit: `+3`
- cluster membership: `+1`
- evidence section hit: `+1`
- evidence bullet hit: `+bullet_count`
- final score capped to a small max such as `7`

### Done when

- the frontend can derive a stable `chapter_id -> hit metadata` map from one `/ask` response
- no graph rendering is changed yet

## Commit 02

### `feat(frontend): feed ask hit map into graph node rendering`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- graph rendering files under `frontend/graph-core-dist/` only if required by the current rendering boundary

### Changes

Pass the Phase 1 hit map into the graph render path so nodes can be styled by current-hit score.

This commit should only add render-time consumption of:

- `currentHitScore`
- `isSeed`
- `evidenceBulletCount`

Do not add session heat or persistence.

### Done when

- the graph renderer receives current-response hit metadata
- rendering can distinguish highlighted vs non-highlighted nodes

## Commit 03

### `feat(frontend): add intensity-based node highlight styling`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- graph rendering files under `frontend/graph-core-dist/` as needed
- [index.html](C:/Users/hy/ChapterGraph/frontend/index.html) only if shared styles are needed

### Changes

Add visible highlight styling driven by `currentHitScore`.

Requirements:

- score `0` keeps the default node appearance
- score `1-2` shows a light highlight
- score `3-4` shows a medium highlight
- score `5+` shows a strong highlight
- seed nodes should read visually stronger than plain cluster neighbors

The style can be implemented with:

- adjusted fill color
- outer ring
- glow alpha

Choose the simplest option that fits the current graph renderer.

### Done when

- latest `/ask` visibly changes the appearance of hit nodes
- highlight strength scales with hit score

## Commit 04

### `feat(frontend): show current-hit details on node hover`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- graph hover rendering code under `frontend/graph-core-dist/` if needed

### Changes

Extend hover content for highlighted nodes.

At minimum show:

- `chapter_id`
- `book_id`
- `currentHitScore`
- `isSeed`
- `evidenceSectionCount`
- `evidenceBulletCount`

Optional for Phase 1:

- `queryType`
- `queryLabel`

Hover should still work for non-highlighted nodes without breaking existing behavior.

### Done when

- highlighted nodes expose current-hit metadata on hover
- hover content is clearly derived from the latest `/ask` only

## Commit 05

### `refactor(frontend): reset and rebuild hit highlight state per ask response`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

### Changes

Make hit highlight state lifecycle explicit:

- rebuild from scratch after each successful `/ask`
- clear or replace old Phase 1 highlight state
- avoid accidental accumulation across requests

This commit exists to make sure Phase 1 stays response-driven and does not silently become session memory.

### Done when

- only the latest `/ask` drives the highlight state
- previous ask highlights do not accumulate

## Commit 06

### `test(frontend): validate phase1 hit map and rendering inputs`

Status: `pending`

### Scope

Files:
- frontend tests if present
- or add small focused tests around the helper logic in the current frontend test setup
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js) only if minor extraction is needed for testability

### Changes

Add focused checks for:

1. seed node gets higher score than cluster-only node
2. evidence bullet count increases score
3. result with no cluster/evidence yields empty or default hit map
4. new `/ask` result replaces the previous Phase 1 hit map

If the frontend test setup is too thin, extract the hit-map builder into a small pure helper and test that directly.

### Done when

- the hit-map scoring logic is covered
- reset behavior is covered

## Commit 07

### `test(smoke): validate phase1 ask hit highlight in the running UI`

Status: `pending`

### Scope

Files:
- no mandatory code change
- optionally small debug output in [app.js](C:/Users/hy/ChapterGraph/frontend/app.js) if needed, but remove if temporary

### Changes

Run the current app locally and verify:

1. term ask highlights current hit nodes
2. chapter ask highlights current hit nodes
3. seed-heavy nodes are visually stronger
4. hover shows current-hit metadata
5. a second ask replaces the first highlight set instead of accumulating

This is a manual smoke / visual validation commit.

### Validation

Suggested validation path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1
```

Then in the browser:

1. send one term ask
2. inspect highlight intensity
3. hover several hit nodes
4. send one chapter ask
5. confirm highlight state is replaced

### Done when

- Phase 1 behavior is visually confirmed in the live UI

## Execution Notes

### Order matters

Implement in this order:

1. build the hit map
2. wire hit metadata into rendering
3. add visual intensity
4. add hover details
5. make lifecycle response-driven
6. test helper logic
7. do live UI smoke

Reason:

- the data model needs to exist before rendering can consume it
- reset logic should be explicit before Phase 2 adds accumulation

### Architecture principle

Keep Phase 1 local to the latest `/ask` response.

Do not let this series drift into:

- session memory
- localStorage
- Redis
- backend hit-history APIs

Those belong to later phases.

## Bottom Line

Phase 1 should end with:

- a deterministic hit map from the latest `/ask`
- visible score-based node highlight
- current-hit hover details
- no accumulation beyond the latest response
