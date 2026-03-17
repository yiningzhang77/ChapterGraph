import test from "node:test";
import assert from "node:assert/strict";

import { buildAskHitMap } from "./askHitMap.js";

test("seed nodes score higher than cluster-only nodes", () => {
    const hitMap = buildAskHitMap(
        {
            cluster: {
                seed: { seed_chapter_ids: ["book::ch1"] },
                chapters: [
                    { chapter_id: "book::ch1", book_id: "book" },
                    { chapter_id: "book::ch2", book_id: "book" },
                ],
            },
            evidence: {
                sections: [],
                bullets: [],
            },
        },
        { queryType: "term", queryLabel: "Actuator" },
    );

    assert.equal(hitMap["book::ch1"].currentHitScore, 4);
    assert.equal(hitMap["book::ch2"].currentHitScore, 1);
    assert.equal(hitMap["book::ch1"].isSeed, true);
    assert.equal(hitMap["book::ch2"].isSeed, false);
});

test("evidence bullets increase score and counts", () => {
    const hitMap = buildAskHitMap(
        {
            cluster: {
                seed: { seed_chapter_ids: [] },
                chapters: [{ chapter_id: "book::ch1", book_id: "book" }],
            },
            evidence: {
                sections: [{ chapter_id: "book::ch1" }],
                bullets: [
                    { chapter_id: "book::ch1" },
                    { chapter_id: "book::ch1" },
                    { chapter_id: "book::ch1" },
                ],
            },
        },
        { queryType: "term", queryLabel: "JdbcTemplate" },
    );

    assert.equal(hitMap["book::ch1"].currentHitScore, 5);
    assert.equal(hitMap["book::ch1"].evidenceSectionCount, 1);
    assert.equal(hitMap["book::ch1"].evidenceBulletCount, 3);
});

test("missing cluster and evidence returns empty map", () => {
    assert.deepEqual(buildAskHitMap(null), {});
    assert.deepEqual(buildAskHitMap({}), {});
});

test("new result produces a separate hit map without accumulation", () => {
    const firstMap = buildAskHitMap(
        {
            cluster: {
                seed: { seed_chapter_ids: ["book::ch1"] },
                chapters: [{ chapter_id: "book::ch1", book_id: "book" }],
            },
            evidence: { sections: [], bullets: [{ chapter_id: "book::ch1" }] },
        },
        { queryType: "term", queryLabel: "Spring" },
    );
    const secondMap = buildAskHitMap(
        {
            cluster: {
                seed: { seed_chapter_ids: ["book::ch2"] },
                chapters: [{ chapter_id: "book::ch2", book_id: "book" }],
            },
            evidence: { sections: [], bullets: [] },
        },
        { queryType: "chapter", queryLabel: "book::ch2" },
    );

    assert.ok(firstMap["book::ch1"]);
    assert.equal(secondMap["book::ch1"], undefined);
    assert.equal(secondMap["book::ch2"].queryType, "chapter");
    assert.equal(secondMap["book::ch2"].queryLabel, "book::ch2");
});
