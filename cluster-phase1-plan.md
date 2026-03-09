# cluster-phase1-plan.md

Date: 2026-03-09  
Target: comprehensive implementation of point-4 in `cluster-research.md` (lines 138-176), i.e. make data shape truly support `chapter -> section -> bullet -> source_refs` indexing flow.

## 0. Plan position

This plan is intentionally **not** the "Phase A fast/low-risk" path.

It is a **comprehensive Phase-1 shape migration**:

- adopt structured section/bullet model as first-class payload
- make `chapter_index_text` the canonical coarse-retrieval text
- preserve raw + normalized forms per section/bullet
- delete `signals` from enriched JSON contract
- include `source_refs` now (allowed to be `null` temporarily)

## 1. Target end-state (must-have)

By end of this phase, every enriched chapter should satisfy:

1. `chapter_index_text` exists and is deterministic.
2. `sections` is structured objects (not string list), and this is the only accepted enrichment shape.
3. each section contains nested `bullets[]` objects (not flat bullet lists).
4. section/bullet keep both raw and normalized forms.
5. each bullet has `source_refs` field (nullable for now).
6. `signals` is removed from enriched JSON and no longer used by retrieval.
7. all regenerated `output/*_enriched.json` files use this same structure.
8. `/ask` can return chapter + section + bullet evidence candidates from current DB data (even when `source_refs` is null).

## 2. Canonical data contract v2

## 2.1 Enriched chapter shape

```json
{
  "id": "spring-in-action::ch3",
  "book_id": "spring-in-action",
  "title": "Working with data",
  "chapter_index_text": "section:reading and writing data with jdbc bullet:working with jdbctemplate ...",
  "sections": [
    {
      "section_id": "spring-in-action::ch3::s1",
      "order": 1,
      "title_raw": "3.1 Reading and writing data with JDBC",
      "title_norm": "Reading and writing data with JDBC",
      "bullets": [
        {
          "bullet_id": "spring-in-action::ch3::s1::b1",
          "order": 1,
          "text_raw": "3.1.1 Working with JdbcTemplate",
          "text_norm": "Working with JdbcTemplate",
          "source_refs": null
        }
      ]
    }
  ]
}
```

Mandatory constraints for this shape:

- `sections` cannot contain plain strings.
- `bullets` cannot live as a top-level flat list.
- every `sections[i]` must include: `section_id`, `order`, `title_raw`, `title_norm`, `bullets`.
- every `bullets[j]` must include: `bullet_id`, `order`, `text_raw`, `text_norm`, `source_refs`.

## 2.2 `chapter_text` policy in this phase

- `chapter_text` is no longer treated as business-semantic field.
- canonical retrieval field becomes `chapter_index_text`.
- for compatibility with old code paths, we can set:
  - `chapter_text = chapter_index_text` during transition window
- after all callers migrate, `chapter_text` can be deprecated.

## 2.3 `chapter_index_text` complete reference (based on current `output/*_enriched.json`)

Use this exact build policy so output is deterministic and reproducible.

Source fields:

- `book_id`
- `chapter.id`
- `chapter.title`
- `sections[].title_norm` (or normalized section string from old JSON)
- `bullets[].text_norm` (or normalized bullet string from old JSON)

Assembly order:

1. `book:{book_norm}`
2. `chapter:{chapter_id_norm}`
3. `title:{chapter_title_norm}`
4. each section in order: `section:{section_norm}`
5. each bullet in order: `bullet:{bullet_norm}`
6. if no bullets exist: append `bullet:none`

Normalization rule (`*_norm`):

- Unicode normalize (`NFKC`)
- lowercase
- strip numeric prefixes for raw lines:
  - section raw prefix: `^\d+\.\d+\s+`
  - bullet raw prefix: `^\d+\.\d+\.\d+\s+`
- replace non-alnum chars with space (keep digits and letters)
- collapse repeated spaces to one
- trim

Example A (`output/spring-in-action_enriched.json`, `spring-in-action::ch1`):

```text
book:spring in action chapter:spring in action ch1 title:getting started with spring section:what is spring section:initializing a spring application section:writing a spring application section:surveying the spring landscape bullet:initializing a spring project with spring tool suite bullet:examining the spring project structure bullet:handling web requests bullet:defining the view bullet:testing the controller bullet:building and running the application bullet:getting to know spring boot devtools bullet:let s review bullet:the core spring framework bullet:spring boot bullet:spring data bullet:spring security bullet:spring integration and spring batch bullet:spring cloud bullet:spring native
```

Example B (`output/spring-in-action_enriched.json`, `spring-in-action::ch8`, no bullets):

```text
book:spring in action chapter:spring in action ch8 title:securing rest section:introducing oauth 2 section:creating an authorization server section:securing an api with a resource server section:developing the client bullet:none
```

## 2.4 Definition of done for new enrichment artifact

This phase is not done unless both are true:

1. JSON artifact DoD:
   - each `output/*_enriched.json` chapter follows `sections[].bullets[]`
   - no `signals` key exists

2. Runtime DoD:
   - DB rows imported from those JSON files preserve the same nesting
   - `/ask` section/bullet localization uses this nesting directly

## 3. Required code changes (comprehensive)

## 3.1 ingestion layer (`feature_achievement/ingestion.py`)

Goals:

- preserve raw numbered text before normalization
- generate section IDs and bullet IDs deterministically
- attach bullets under sections
- produce `sections[].bullets[]` as the canonical enrichment output shape

Changes:

- section parser returns object with `title_raw`, `title_norm`, `section_id`, `order`, `bullets=[]`
- bullet parser returns object with `text_raw`, `text_norm`, `bullet_id`, `order`, `source_refs=None`
- stop producing `signals` in enriched JSON output

## 3.2 enrichment layer (`feature_achievement/enrichment.py`)

Goals:

- build deterministic `chapter_index_text`

Implementation rule:

- concatenate normalized section/bullet lines with explicit tags:
  - `section:{title_norm}`
  - `bullet:{text_norm}`

This is the only field used for coarse retrieval in ask path.

## 3.3 DB model + persistence

Files:

- `feature_achievement/db/models.py`
- `feature_achievement/db/crud.py`
- migration script in `feature_achievement/scripts/`

Changes:

- add `chapter_index_text: str` to `EnrichedChapter`
- keep `sections` as JSON (now object-rich)
- remove `signals` from model/persistence path (and DB column once migration is done)
- update `persist_enriched_chapters()` to write new shape
- backfill script reads existing JSON and produces v2 shape

## 3.4 ask query path

Files:

- `feature_achievement/db/ask_queries.py`
- `feature_achievement/ask/cluster_builder.py`
- `feature_achievement/api/schemas/ask.py` (optional flags)

Changes:

1. term seed search should target `chapter_index_text` instead of old `chapter_text`.
2. add in-memory local ranking helpers per selected chapter:
   - `rank_sections_local(query, sections, top_k)`
   - `rank_bullets_local(query, sections, top_k)`
3. cluster output supports evidence preview fields:
   - `sections` candidates
   - `bullets` candidates (`source_refs` may be null)

## 3.5 `/ask` response contract (this phase)

Add optional evidence object:

```json
{
  "cluster": {...},
  "evidence": {
    "sections": [
      {"section_id":"...","title_norm":"...","score":0.73}
    ],
    "bullets": [
      {"bullet_id":"...","text_norm":"...","score":0.82,"source_refs":null}
    ]
  }
}
```

LLM prompt continues to use bounded context, but now prefer bullet-level evidence text over raw chapter blob.

## 4. Migration and backfill strategy

## 4.1 One-time migration script

Create: `feature_achievement/scripts/migrate_enriched_shape_v2.py`

Responsibilities:

1. read current enriched chapter rows
2. transform old `sections: list[str]` + `signals.bullets: list[str]` into v2 structure
3. compute `chapter_index_text`
4. set `source_refs=null` for all bullets (temporary by design)
5. remove `signals` payload from written JSON rows
6. write back with `overwrite=True`
7. verify each regenerated JSON file has `sections[].bullets[]` shape before DB import

## 4.2 Versioning

Use new enrichment version string for this schema, e.g.:

- `v2_indexed_sections_bullets`

Then run normalization/selection logic accordingly in `/ask` request default only after validation.

## 5. Testing and verification

## 5.1 Unit tests

Add/extend tests for:

- section/bullet ID determinism
- raw vs norm preservation
- chapter_index_text deterministic generation
- seed search uses chapter_index_text
- section/bullet ranking output shape
- `signals` key absent from enriched JSON outputs
- source_refs nullable behavior

## 5.2 Integration tests

- `/ask` term returns cluster + evidence sections/bullets
- `/ask` chapter returns same shape
- with `source_refs=null`, answer path still works and no crash

## 5.3 Smoke

Extend smoke scripts:

- print section_count and bullet_count in evidence
- verify `signals` is absent in migrated enriched payload
- validate every returned bullet has `source_refs` key (nullable accepted)

## 6. Execution sequence (no low-risk branch)

1. Implement ingestion v2 structure.
2. Implement enrichment `chapter_index_text` builder.
3. Regenerate all `output/*_enriched.json` with `sections[].bullets[]` and no `signals`.
4. Add DB model field + migration script.
5. Backfill/import enriched data to v2.
6. Switch ask retrieval to `chapter_index_text`.
7. Add section/bullet localizers + evidence response.
8. Update tests + smoke.
9. Flip default enrichment version to v2 once smoke passes.

## 7. Risks and controls

Risk 1: Existing consumers assume `sections` is list[str].

- Control: update all in-repo consumers in same change-set; do not partial ship.

Risk 2: Existing code/scripts still read `signals.bullets` or `signals.raw_text`.

- Control: remove all in-repo references in same PR and replace with structured section/bullet traversal.
- Control: add a migration-check test that fails if any runtime path reads `signals`.

Risk 3: ranking quality drops when normalization is too aggressive.

- Control: keep both raw/norm and include deterministic tags in `chapter_index_text`.

Risk 4: historic artifacts in `output/*_enriched.json` and DB rows become mixed schema.

- Control: one-time full backfill + version bump (`v2_indexed_sections_bullets`) and reject old version in new path.

Risk 5: no source mapping yet.

- Control: enforce field existence with nullable `source_refs`; build downstream code to tolerate null and continue.

## 8. Acceptance criteria (phase complete)

Phase is complete only if all hold:

1. every enriched chapter row has non-empty `chapter_index_text`
2. `sections` are structured objects with nested `bullets[]` (no string sections)
3. `signals` is absent in enriched JSON and not used by runtime code
4. each bullet has `text_raw`, `text_norm`, and `source_refs` key (nullable)
5. regenerated `output/*_enriched.json` all pass schema check
6. `/ask` retrieval uses `chapter_index_text`
7. `/ask` response includes section/bullet evidence candidates
8. tests and smoke pass

This gives you a full index-shape foundation for the next step (`source_refs` population + true source snippet retrieval) without reverting to the low-risk compatibility-only route.
