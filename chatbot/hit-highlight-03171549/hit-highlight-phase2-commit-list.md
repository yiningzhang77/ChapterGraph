2026-03-17 15:10

# Hit Highlight Phase 2 Commit List

This document turns Phase 2 of [hit-highlight-plan.md](C:/Users/hy/ChapterGraph/chatbot/hit-highlight-03171549/hit-highlight-plan.md) into an implementation sequence.

Goal:

- accumulate repeated node hits across multiple asks in the same browser session
- keep current-response highlight and session heat separate
- expose session hit information in hover
- avoid persistence, Redis, or backend memory in this phase

Phase 2 is still frontend-local.
It should survive multiple asks during one page runtime, but it does not need to survive reloads.

## Commit 01

### `feat(frontend): add session hit history state for chapter nodes`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [askHitMap.js](C:/Users/hy/ChapterGraph/frontend/askHitMap.js) only if shared helper logic needs extraction

### Changes

Add a frontend state map for accumulated session history.

Suggested shape:

```javascript
{
  "spring-in-action::ch3": {
    sessionHitCount: 4,
    lastHitAt: 1710000000000
  }
}
```

This state should be independent from the current-response hit map.

### Done when

- the frontend can track cumulative chapter hits across multiple asks in the same session
- no rendering changes yet

## Commit 02

### `feat(frontend): increment session hit history from current ask results`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

### Changes

After each successful `/ask`:

- read the current-response hit map
- increment `sessionHitCount` for every hit chapter
- update `lastHitAt`

Keep the first version simple:

- no decay
- no weighting by query type
- no pruning

### Done when

- multiple asks cause repeated chapter hits to accumulate in local session state

## Commit 03

### `feat(frontend): merge current-hit and session-hit data for graph rendering`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [graph-core/buildView.ts](C:/Users/hy/ChapterGraph/frontend/graph-core/buildView.ts)
- [graph-core/types.ts](C:/Users/hy/ChapterGraph/frontend/graph-core/types.ts)
- generated `graph-core-dist/*` files after build

### Changes

Extend the chapter-node render payload so it contains both:

- current-response hit data
- session hit data

Suggested render shape:

```javascript
askHit: {
  currentHitScore,
  isSeed,
  evidenceSectionCount,
  evidenceBulletCount,
  queryType,
  queryLabel,
  sessionHitCount,
  lastHitAt
}
```

Do not collapse session heat into current score.

### Done when

- render-time node data clearly separates current-hit from session-hit

## Commit 04

### `feat(frontend): add session heat visual channel on top of current highlight`

Status: `completed`

### Scope

Files:
- [graph-core/buildView.ts](C:/Users/hy/ChapterGraph/frontend/graph-core/buildView.ts)
- generated `graph-core-dist/*` files after build

### Changes

Keep current-response intensity as the main signal.
Add a second visual cue for session accumulation.

Examples:

- thicker outer aura for higher `sessionHitCount`
- secondary ring
- stronger glow thickness

The key requirement is visual separation:

- current request highlight != session memory heat

### Done when

- repeated hits look meaningfully hotter than one-off hits
- users can still distinguish current-hit intensity from session accumulation

## Commit 05

### `feat(frontend): add session hit details to hover panel`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

### Changes

Extend the chapter hover block with:

- `sessionHitCount`
- `lastHitAt` or a simple readable derivative if useful

Current-hit details from Phase 1 should remain visible.

### Done when

- hover clearly shows both current-hit data and session-hit data

## Commit 06

### `refactor(frontend): define reset boundaries for session heat`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

### Changes

Explicitly decide when session accumulation resets.

Recommended Phase 2 rule:

- preserve session history across asks within the current page runtime
- reset when the user reloads the page
- reset when changing `run_id`

This keeps Phase 2 scoped to one active graph session.

### Done when

- reset behavior is deterministic and intentional
- session heat does not bleed across runs

## Commit 07

### `test(frontend): cover session hit accumulation behavior`

Status: `completed`

### Scope

Files:
- add or extend pure frontend helper tests
- [askHitMap.js](C:/Users/hy/ChapterGraph/frontend/askHitMap.js) only if helper extraction is useful
- add a session-hit helper module if that improves testability

### Changes

Cover at least:

1. first hit creates `sessionHitCount = 1`
2. repeated hit increments count
3. different chapters accumulate independently
4. run change clears session heat
5. current-hit replacement does not erase accumulated session heat for still-active run

### Done when

- session accumulation logic is covered by focused tests

## Commit 08

### `test(smoke): validate session heat behavior in the running UI`

Status: `pending`

### Scope

Files:
- no mandatory code change

### Changes

Run the app locally and verify:

1. first ask highlights current-hit nodes
2. second related ask increases session heat on overlapping nodes
3. hover shows increased `sessionHitCount`
4. changing run clears session heat
5. reload still clears everything in Phase 2

### Validation

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1
node --test frontend/askHitMap.test.js
```

Then verify in the browser:

1. send two related asks
2. inspect hotter repeated nodes
3. hover repeated nodes
4. switch run
5. confirm heat reset

### Done when

- session-level accumulation is visually confirmed without any persistence layer

## Execution Notes

### Order matters

Implement in this order:

1. add session state
2. accumulate from ask results
3. merge into render payload
4. add session visual channel
5. extend hover
6. define reset boundaries
7. test helper logic
8. do live UI smoke

Reason:

- state semantics need to exist before rendering can reflect them
- reset policy should be explicit before Phase 3 adds persistence

### Architecture principle

Keep Phase 2 strictly browser-session local.

Do not introduce:

- localStorage
- Redis
- backend trace APIs
- shared multi-user state

Those belong to Phase 3.

## Bottom Line

Phase 2 should end with:

- repeated asks increasing node heat within one browser session
- hover showing both current-hit and session-hit data
- deterministic reset on run change
- no persistence beyond the page runtime
