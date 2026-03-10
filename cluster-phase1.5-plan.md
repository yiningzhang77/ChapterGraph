# cluster-phase1.5-plan.md

Date: 2026-03-10
Target: implement a probe-first EPUB parser adapter that can populate `source_refs` for the current Graph-RAG enrichment shape (`sections[].bullets[]`), and only harden adapter logic for EPUB types we have actually encountered. Hard parsing cases may be skipped in auto-parse and backfilled manually.

## 0. Scope and constraints

- Keep current `/ask` and edge pipeline contract stable.
- Do not open generic user-upload ingestion in this phase.
- Focus on EPUB-only adapter and `source_refs` population.
- Add `epub_probe` as the first mandatory step for every new EPUB.
- Keep `chapter_index_text` generation unchanged.
- `source_refs` can still be `null` only when anchor mapping fails, but failures must be measurable.
- Allow controlled manual backfill for hard slices instead of blocking whole-book import.

## 0.1 Execution status (2026-03-10)

- Completed: commit `01` to `12` in `cluster-phase1.5-commit-list.md`.
- Current capability:
  - probe-first EPUB routing for encountered types A/B/C
  - outline extraction + anchor slicing + source_refs generation
  - unresolved export + manual backfill patch script
  - EPUB source_refs smoke and ask-path smoke
- Operational guardrail remains: if mapping is not reliable, mark unresolved and backfill manually instead of adding ad-hoc parser heuristics.

## 0.2 Phase 1.5 runbook (actual)

1. Probe EPUB type:
   - `python -m feature_achievement.scripts.probe_epub --epub <path_to_epub>`
2. Build enriched JSON from EPUB:
   - `python -m feature_achievement.scripts.build_enriched_from_epub --epub <path_to_epub> --book-id <book_id> --output <output_json> --unresolved-output tmp/source_refs_needs_manual.json`
3. Smoke source_refs quality:
   - `python -m feature_achievement.scripts.smoke_epub_source_refs`
4. If unresolved exists, patch manually:
   - `python -m feature_achievement.scripts.apply_source_refs_manual_patch --enriched <output_json> --patch <manual_patch_json> --output <patched_output_json>`
5. Validate and import into DB:
   - `python -m feature_achievement.scripts.validate_enriched_v2 --input <patched_output_json>`
   - `python -m feature_achievement.scripts.import_enriched_chapters --input <patched_output_json> --overwrite --enrichment-version v2_indexed_sections_bullets`
6. Verify ask evidence path:
   - `python -m feature_achievement.scripts.smoke_ask_cluster`

## 0.3 Escalation rule (do not overfit parser)

- Do not add book-specific parser hacks after one deterministic fallback attempt.
- If a slice fails to map reliably:
  - keep `source_refs=null`
  - append to `tmp/source_refs_needs_manual.json`
  - continue pipeline
- Only extend parser strategy when probe classification itself is wrong for a repeated EPUB layout type.

## 1. Sample EPUB findings (encountered types)

## 1.1 Type A (already analyzed)

Sample file:

- `book_epub/spring_in_action/Spring in Action, Sixth Edition ... .epub`

Observed structure after unzip:

- `content.opf` (EPUB2 package)
- `toc.ncx` (nested TOC with chapter/section/subsection numbering)
- `index_split_000.html` ... `index_split_008.html`
- `index_split_008.html` contains `Document Outline` as nested `<ul><li><a href="index_split_xxx.html#pNN">...`
- body content uses anchor IDs like `#p414`, `#p415`

Important quirks in this sample:

- likely converted by `pdftohtml` + calibre
- header/footer repeats (`CHAPTER 15`, chapter title line, page number lines)
- encoding artifacts (`鈥`, `飩?`)

Type A signature:

- root-level split files: `index_split_000.html` ... `index_split_008.html`
- page-like anchors: `#pNNN`
- usable outline in `index_split_008.html`

## 1.2 Type B (already analyzed)

Sample file:

- `book_epub/spring_start_here/Spring Start Here ... .epub`

Observed structure after unzip:

- `META-INF/container.xml` -> `OEBPS/content.opf`
- chapter files like `OEBPS/ch01.htm` ... `OEBPS/ch15.htm`
- nested TOC in `OEBPS/toc.ncx`
- additional HTML TOC in `OEBPS/Spilca_TOC.htm`
- semantic anchors like `#sigil_toc_id_11`, `#pgfId-998521`

Type B signature:

- `OEBPS/` directory layout
- chapter-per-file naming (`chNN.htm`)
- anchor IDs are semantic/editor-generated, not page-like

## 1.3 Type C (newly uploaded, final book)

Sample file:

- `book_epub/springboot_in_action/Spring Boot in Action ... .epub`

Observed structure after unzip:

- root-level `content.opf` + `toc.ncx`
- content files in `OEBPS/Text/01.html` ... `08.html` + appendixes
- chapter files with semantic HTML headings (`h1/h2/h3`) and internal anchors (`heading_id_x`, `ID_x`)
- TOC depth is mostly chapter-level in `toc.ncx`; subsection anchors are sparse

Type C signature:

- `OEBPS/Text/*.html` layout
- chapter-first TOC (low subsection coverage)
- subsection signals mostly from body headings, not TOC tree

Compatibility implication:

- Type A/B-specific rules are not enough for all books.
- We need a probe + dispatch router to select parser strategy by type.

## 2. Adapter architecture (probe-first)

## 2.0 Mandatory probe stage

Add:

- `feature_achievement/epub/probe.py`
- `feature_achievement/scripts/probe_epub.py`

`probe_epub` output should include:

- `epub_version`: epub2/epub3 heuristic
- `rootfile_path` from `container.xml`
- `toc_sources`: `nav.xhtml` / `toc.ncx` / html-outline candidates
- `content_layout_type`:
  - `type_a_split_pages` (Spring in Action style)
  - `type_b_chapter_files` (Spring Start Here style)
  - `type_c_text_dir_chapters` (Spring Boot in Action style)
  - `unknown`
- `anchor_style`:
  - `pNN`
  - `sigil_toc_id`
  - `heading_id`
  - mixed
- `chapter_file_pattern` and counts
- `confidence` and `selected_strategy`

Routing rule:

1. Run probe.
2. Select parser strategy from detected type.
3. Parse and emit metrics.
4. If probe confidence too low, fail fast and require rule extension (do not silently degrade).

## 2.1 New module layout

Add:

- `feature_achievement/epub/adapter.py`
- `feature_achievement/epub/probe.py`
- `feature_achievement/epub/outline.py`
- `feature_achievement/epub/content.py`
- `feature_achievement/epub/source_refs.py`
- `feature_achievement/scripts/build_enriched_from_epub.py`
- `feature_achievement/scripts/probe_epub.py`
- `feature_achievement/scripts/apply_source_refs_manual_patch.py`

Keep existing ingestion for `.txt` unchanged.

## 2.2 Stable internal contracts

```python
from dataclasses import dataclass

@dataclass
class TocNode:
    level: int
    title: str
    href_file: str
    href_anchor: str | None

@dataclass
class AnchorSlice:
    file: str
    start_anchor: str
    end_anchor: str | None
    text: str
```

Output still follows v2 chapter shape:

- `sections[].bullets[]`
- each bullet has `source_refs: list[dict] | None`

## 3. Parse strategy (by detected type)

## 3.1 TOC source priority

For `type_a_split_pages`:

1. Parse `index_split_008.html` Document Outline first.
2. Fallback to `toc.ncx`.
3. Fallback to body regex scan.

For `type_b_chapter_files`:

1. Parse `toc.ncx` first.
2. Fallback to `Spilca_TOC.htm` style HTML TOC.
3. Fallback to chapter heading scan in `chNN.htm`.

For `type_c_text_dir_chapters`:

1. Parse chapter list from `toc.ncx` / `navDisplay.html`.
2. For each chapter file, extract section/bullet hierarchy from in-body `h2/h3` plus numeric heading text.
3. If heading anchors are missing, build synthetic anchors from nearest preceding element ID.

Reason:

- Type A outline HTML is high quality.
- Type B `toc.ncx` is structured down to subsection level.
- Type C has clean chapter files but weaker subsection-level TOC, so body heading extraction is required.

## 3.2 Heading classification

Use deterministic regex:

- Chapter: `^(\d+)\s+(.+)$`
- Section: `^(\d+\.\d+)\s+(.+)$`
- Bullet: `^(\d+\.\d+\.\d+)\s+(.+)$`

Ignore items:

- `Part ...`
- `Summary`
- front matter (`preface`, `acknowledgments`, `about ...`)

Normalization:

- Unicode NFKC
- normalize mojibake punctuation where possible
- trim spaces

## 3.3 Anchor-to-text slicing

For each TOC node `(file, start_anchor)`:

1. Find start element by `id=start_anchor`.
2. End at next TOC anchor in same reading order.
3. Collect text from paragraph-like nodes in between.
4. Clean noise lines:
   - page-number-only lines (`^\d+$`)
   - `CHAPTER \d+`
   - repeated chapter-title running headers
   - isolated decorative bullets (`飩?`)
5. Join wrapped lines into paragraph blocks.

Hard-case rule:

- If slice cannot be reliably delimited, mark as `parse_status=needs_manual_ref` and keep `source_refs=null` temporarily.

## 3.4 source_refs generation policy

For each bullet node:

- Resolve its text slice using anchor range.
- Save first high-signal snippet (for MVP one snippet per bullet is enough).
- Build deterministic ref object:

```json
{
  "format": "epub_anchor_v1",
  "file": "OEBPS/Text/07.html",
  "start_anchor": "heading_id_42",
  "end_anchor": "heading_id_43",
  "selector": {"type": "id_range", "start": "heading_id_42", "end": "heading_id_43"},
  "snippet": "...",
  "confidence": 0.93
}
```

For section-level fallback (no bullet anchor), allow:

- map section anchor range
- assign section snippet to all child bullets only if bullet anchors missing
- set `confidence` lower

Manual override schema:

```json
{
  "chapter_id": "springboot-in-action::ch7",
  "bullet_id": "springboot-in-action::ch7::s2::b3",
  "source_refs": [
    {
      "format": "epub_anchor_v1",
      "file": "OEBPS/Text/07.html",
      "start_anchor": "heading_id_42",
      "end_anchor": "heading_id_43",
      "selector": {"type": "id_range", "start": "heading_id_42", "end": "heading_id_43"},
      "snippet": "...",
      "confidence": 0.95,
      "origin": "manual_patch"
    }
  ]
}
```

## 4. Sample-specific parse plan

## 4.1 Type A concrete mapping example (chapter 15)

- chapter: `spring-in-action::ch15` -> `index_split_006.html#p414`
- section: `15.1 Introducing Actuator` -> `#p415`
- bullet: `15.1.1 ...` -> `#p416`
- bullet slice: `#p416` to before `#p417`

## 4.2 Type B concrete mapping example (chapter 1)

From `toc.ncx`:

- chapter: `1 Spring in the real world` -> `ch01.htm`
- section: `1.1 Why should we use frameworks?` -> `ch01.htm#sigil_toc_id_11`
- bullet: `1.2.1 Discovering Spring Core...` -> `ch01.htm#sigil_toc_id_13`

## 4.3 Type C concrete mapping approach

- chapter root: from `toc.ncx` chapter entries (`OEBPS/Text/NN.html`)
- section detection: `h2` text that matches `^\d+\.\d+`
- bullet detection: `h3` text that matches `^\d+\.\d+\.\d+`
- fallback: parse numbered heading text embedded in paragraph nodes
- if none of the above is reliable, defer to manual backfill list

## 4.4 Noise handling

- Remove header/footer repeats and standalone page numbers.
- Skip table/listing captions as primary snippet candidates.
- Keep code/config lines if they are inside bullet range.

## 5. Integration with current enrichment pipeline

## 5.1 Minimal invasive route

- Add a new script:
  - `python -m feature_achievement.scripts.build_enriched_from_epub --epub ... --book-id ...`
- Script outputs v2 enriched JSON directly:
  - `chapter_index_text`
  - structured `sections[].bullets[]`
  - populated `source_refs`

No change required for:

- `ask` request schema
- edge computation algorithm
- cluster builder interfaces

## 5.2 Data import path

Reuse existing:

- `validate_enriched_v2`
- `import_enriched_chapters --overwrite`
- `normalize_enrichment_version`

## 6. Verification plan

## 6.1 Unit tests

Add:

- probe classification tests:
  - Type A sample detected as `type_a_split_pages`
  - Type B sample detected as `type_b_chapter_files`
  - Type C sample detected as `type_c_text_dir_chapters`
- TOC parser tests:
  - Type A: `index_split_008.html` hierarchy depth
  - Type B: `toc.ncx` hierarchy depth
  - Type C: chapter-level TOC extraction + body heading-derived subsection extraction
- anchor slice extraction tests:
  - Type A: `p416 -> p417`
  - Type B: `sigil_toc_id_13 -> next`
  - Type C: `heading_id_x -> heading_id_y`
- noise-cleaning test for repeated headers/page numbers
- `source_refs` schema test (`format/file/start_anchor/end_anchor/snippet`)
- manual patch merge test (manual refs override null refs deterministically)

## 6.2 Smoke tests

Add:

- `python -m feature_achievement.scripts.smoke_epub_source_refs`

Checks:

- at least one chapter has non-empty bullet `source_refs`
- coverage ratio:
  - `bullets_with_source_refs / total_bullets >= 0.7` for Type A sample
  - `bullets_with_source_refs / total_bullets >= 0.7` for Type B sample
  - `bullets_with_source_refs / total_bullets >= 0.6` for Type C sample (auto only)
- probe output exists and selected strategy matches expectation
- unresolved list exported for manual fill:
  - `tmp/source_refs_needs_manual.json`

## 6.3 Ask-path verification

Run:

- `python -m feature_achievement.scripts.smoke_ask_cluster`

Expect:

- evidence bullets returned
- sampled evidence bullets have non-null `source_refs`

## 7. Delivery sequence (Phase 1.5)

1. Implement `epub_probe` and parser strategy router.
2. Implement Type A strategy (`index_split_008` + `pNN` anchors).
3. Implement Type B strategy (`toc.ncx` + `sigil_toc_id` anchors).
4. Implement Type C strategy (`OEBPS/Text/*.html` chapter TOC + body heading extraction).
5. Implement shared anchor slicing and text cleaning.
6. Implement `source_refs` builder and schema.
7. Implement manual patch apply flow (`needs_manual_ref` export + patch import).
8. Generate enriched JSON for all uploaded EPUBs.
9. Validate + import to DB + normalize version.
10. Add tests and smoke.
11. Verify `/ask` evidence contains non-null `source_refs`.

## 8. Definition of done (Phase 1.5)

Phase 1.5 is complete only if all hold:

1. EPUB adapter can parse encountered EPUB types deterministically.
2. Probe can classify encountered EPUB types and route parser strategy correctly.
3. Generated enriched JSON remains v2-compatible.
4. For all encountered types, `source_refs` coverage targets are met.
5. `/ask` evidence returns bullet `source_refs` from DB data.
6. Existing non-EPUB pipelines are not regressed.
7. Any unresolved auto-parse slices are explicitly listed and can be backfilled via manual patch script.

## 9. Explicit non-goals

- Generic end-user upload API and multi-tenant run isolation.
- PDF parser.
- Agentic orchestration redesign.

Those can be Phase 2+ after EPUB source-ref pipeline is stable.
