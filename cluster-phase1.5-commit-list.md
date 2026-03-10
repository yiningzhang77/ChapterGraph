# cluster-phase1.5-commit-list.md

Date: 2026-03-10  
Goal: Implement `cluster-phase1.5-plan.md` with a probe-first EPUB adapter that fills `source_refs` for encountered EPUB types, while explicitly avoiding parser over-engineering.

## Execution Principle (must hold for every commit)

- Avoid parser quicksand: if one slice cannot be mapped reliably, mark it unresolved and continue.
- Manual backfill is a first-class path, not a failure path.
- Keep `/ask`, edge pipeline, and non-EPUB ingestion stable.
- Every commit must have a runnable verification command.

## Progress Snapshot

- Planned commits: `01` to `12`
- Completed: `01`, `02`
- In progress: none

---

## [x] Commit 01 - `feat(epub-probe): add mandatory EPUB probe and strategy classification`

Purpose:
- Add a deterministic probe step before parsing.

Changes:
- add `feature_achievement/epub/probe.py`
- add `feature_achievement/scripts/probe_epub.py`
- classify:
  - `type_a_split_pages`
  - `type_b_chapter_files`
  - `type_c_text_dir_chapters`
  - `unknown`
- emit `confidence`, `selected_strategy`, `anchor_style`, `toc_sources`

Verify:
- `python -m feature_achievement.scripts.probe_epub --epub <path>`
- three known books are classified to expected type

---

## [x] Commit 02 - `feat(epub-outline): implement TOC extraction with per-type priority`

Purpose:
- Build unified outline extraction without mixing type-specific heuristics.

Changes:
- add `feature_achievement/epub/outline.py`
- implement per-type TOC priority:
  - Type A: `index_split_008.html` -> `toc.ncx` -> regex fallback
  - Type B: `toc.ncx` -> `Spilca_TOC.htm` -> heading scan
  - Type C: `toc.ncx` / `navDisplay.html` -> body heading scan
- normalize href into `(file, anchor)`

Verify:
- unit tests for outline depth and chapter count on all three samples

---

## [ ] Commit 03 - `feat(epub-content): add anchor slicing and noise cleaning core`

Purpose:
- Implement shared text slicing logic from anchor range.

Changes:
- add `feature_achievement/epub/content.py`
- implement:
  - `find_anchor_start`
  - `find_anchor_end`
  - `extract_text_between_anchors`
  - deterministic cleaners for page/header/footer noise
- return structured slice metadata + cleaned text

Verify:
- tests for representative ranges:
  - `pNN` style
  - `sigil_toc_id` style
  - `heading_id` style

---

## [ ] Commit 04 - `feat(epub-source-refs): build source_refs with confidence and deterministic schema`

Purpose:
- Generate `source_refs` objects from resolved slices.

Changes:
- add `feature_achievement/epub/source_refs.py`
- emit `format/file/start_anchor/end_anchor/selector/snippet/confidence`
- support section-level fallback when bullet anchor is missing

Verify:
- schema tests pass for generated refs
- sample chapters produce non-empty refs where anchors resolve

---

## [ ] Commit 05 - `feat(epub-adapter): add parser router and unified adapter entry`

Purpose:
- Wire probe + outline + content + source_refs into one adapter pipeline.

Changes:
- add `feature_achievement/epub/adapter.py`
- add router by `selected_strategy`
- return:
  - enriched chapter payload (v2 shape)
  - parse metrics
  - unresolved refs list

Verify:
- adapter runs on all three EPUBs and outputs parse report JSON

---

## [ ] Commit 06 - `feat(script): add build_enriched_from_epub pipeline script`

Purpose:
- Produce import-ready enriched JSON from EPUB.

Changes:
- add `feature_achievement/scripts/build_enriched_from_epub.py`
- output:
  - `chapter_index_text`
  - `sections[].bullets[]`
  - `source_refs` (nullable when unresolved)
  - `parse_status` and metrics
- keep existing `.txt` ingestion unchanged

Verify:
- script generates output JSON for each uploaded EPUB
- `chapter_index_text` remains deterministic

---

## [ ] Commit 07 - `feat(manual-backfill): export unresolved list and patch apply script`

Purpose:
- Make "skip hard parse + manual fill" operational.

Changes:
- add unresolved export:
  - `tmp/source_refs_needs_manual.json`
- add `feature_achievement/scripts/apply_source_refs_manual_patch.py`
- manual patch input schema:
  - `chapter_id`
  - `bullet_id`
  - `source_refs[]`
- merge policy: manual refs override null refs deterministically

Verify:
- run patch script on a small sample patch file
- verify patched bullets now contain non-null `source_refs`

---

## [ ] Commit 08 - `test(epub): add probe/outline/slice/source_refs unit coverage`

Purpose:
- Lock in deterministic behavior and prevent parser drift.

Changes:
- add tests:
  - `tests/test_epub_probe.py`
  - `tests/test_epub_outline.py`
  - `tests/test_epub_content_slice.py`
  - `tests/test_epub_source_refs.py`
  - `tests/test_epub_manual_patch.py`

Verify:
- `$env:PYTHONPATH='.'; pytest -q`

---

## [ ] Commit 09 - `feat(smoke): add smoke_epub_source_refs with coverage gates`

Purpose:
- Provide fast operational quality check.

Changes:
- add `feature_achievement/scripts/smoke_epub_source_refs.py`
- checks:
  - probe strategy matches expected sample type
  - refs coverage gate:
    - Type A >= 0.7
    - Type B >= 0.7
    - Type C >= 0.6 (auto-only)
  - unresolved list file generated

Verify:
- `python -m feature_achievement.scripts.smoke_epub_source_refs`

---

## [ ] Commit 10 - `chore(import): validate and import EPUB-enriched outputs into DB`

Purpose:
- Move generated data into runtime DB path.

Changes:
- run/adjust:
  - `validate_enriched_v2`
  - `import_enriched_chapters --overwrite`
  - `normalize_enrichment_version`
- ensure imported rows carry new `source_refs`

Verify:
- DB spot check: sampled bullets include `source_refs` or explicit unresolved marker

---

## [ ] Commit 11 - `test(ask-integration): verify /ask evidence includes source_refs after import`

Purpose:
- Confirm the parser work is visible in ask-path evidence.

Changes:
- extend smoke/integration:
  - `feature_achievement/scripts/smoke_ask_cluster.py` assertions for evidence refs
  - optional API-level ask smoke for term + chapter mode

Verify:
- `python -m feature_achievement.scripts.smoke_ask_cluster`
- sampled evidence bullets have non-null `source_refs` where resolved

---

## [ ] Commit 12 - `docs(phase1.5): update phase status, runbook, and unresolved-backfill workflow`

Purpose:
- Close the loop with operational docs.

Changes:
- update `cluster-phase1.5-plan.md` progress/status
- add runbook section:
  - probe -> parse -> smoke -> unresolved export -> manual patch -> re-import
- document "do not overfit parser" rule and escalation criteria for new EPUB types

Verify:
- command list in docs is executable as written

---

## Stop Rules (anti-quicksand guardrails)

- If a new EPUB cannot be confidently classified by probe, stop parser changes and add a probe rule first.
- If a specific anchor range fails after one deterministic fallback, mark unresolved and move on.
- Do not add LLM/tooling redesign in this phase.
- Do not block whole-book import because of a minority unresolved bullets.

## Continuous Checks (every commit)

- `$env:PYTHONPATH='.'; pytest -q`
- `python -m feature_achievement.scripts.probe_epub --epub <sample>`
- `python -m feature_achievement.scripts.smoke_epub_source_refs` (from Commit 09 onward)
