import test from "node:test";
import assert from "node:assert/strict";

import {
    buildAskHitMap,
    mergeAskHitWithSessionHistory,
    updateSessionHitHistory,
} from "./askHitMap.js";

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

test("first hit creates sessionHitCount = 1", () => {
    const currentHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
        },
    };

    const nextHistory = updateSessionHitHistory({}, currentHitMap, 1000);

    assert.deepEqual(nextHistory, {
        "book::ch1": {
            sessionHitCount: 1,
            lastHitAt: 1000,
        },
    });
});

test("repeated hit increments count", () => {
    const currentHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
        },
    };

    const firstHistory = updateSessionHitHistory({}, currentHitMap, 1000);
    const secondHistory = updateSessionHitHistory(firstHistory, currentHitMap, 2000);

    assert.deepEqual(secondHistory, {
        "book::ch1": {
            sessionHitCount: 2,
            lastHitAt: 2000,
        },
    });
});

test("different chapters accumulate independently", () => {
    const firstHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
        },
    };
    const secondHitMap = {
        "book::ch2": {
            chapterId: "book::ch2",
            currentHitScore: 3,
        },
    };

    const firstHistory = updateSessionHitHistory({}, firstHitMap, 1000);
    const secondHistory = updateSessionHitHistory(firstHistory, secondHitMap, 2000);

    assert.deepEqual(secondHistory, {
        "book::ch1": {
            sessionHitCount: 1,
            lastHitAt: 1000,
        },
        "book::ch2": {
            sessionHitCount: 1,
            lastHitAt: 2000,
        },
    });
});

test("run change reset clears session heat in merged render payload", () => {
    const currentHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
        },
    };
    const sessionHistory = updateSessionHitHistory({}, currentHitMap, 1000);

    const mergedBeforeReset = mergeAskHitWithSessionHistory(currentHitMap, sessionHistory);
    const mergedAfterReset = mergeAskHitWithSessionHistory(currentHitMap, {});

    assert.equal(mergedBeforeReset["book::ch1"].sessionHitCount, 1);
    assert.equal(mergedBeforeReset["book::ch1"].lastHitAt, 1000);
    assert.equal(mergedAfterReset["book::ch1"].sessionHitCount, 0);
    assert.equal(mergedAfterReset["book::ch1"].lastHitAt, null);
});

test("current-hit replacement preserves accumulated session heat for same run", () => {
    const firstHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
            queryType: "term",
            queryLabel: "Spring",
        },
    };
    const secondHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 2,
            queryType: "term",
            queryLabel: "JdbcTemplate",
        },
        "book::ch2": {
            chapterId: "book::ch2",
            currentHitScore: 1,
            queryType: "term",
            queryLabel: "JdbcTemplate",
        },
    };

    const firstHistory = updateSessionHitHistory({}, firstHitMap, 1000);
    const secondHistory = updateSessionHitHistory(firstHistory, secondHitMap, 2000);
    const mergedSecondMap = mergeAskHitWithSessionHistory(secondHitMap, secondHistory);

    assert.equal(mergedSecondMap["book::ch1"].currentHitScore, 2);
    assert.equal(mergedSecondMap["book::ch1"].queryLabel, "JdbcTemplate");
    assert.equal(mergedSecondMap["book::ch1"].sessionHitCount, 2);
    assert.equal(mergedSecondMap["book::ch1"].lastHitAt, 2000);
    assert.equal(mergedSecondMap["book::ch2"].sessionHitCount, 1);
});

test("session-only chapters remain in merged render payload after a later ask", () => {
    const firstHitMap = {
        "book::ch1": {
            chapterId: "book::ch1",
            currentHitScore: 4,
            queryType: "term",
            queryLabel: "Spring",
        },
        "book::ch2": {
            chapterId: "book::ch2",
            currentHitScore: 2,
            queryType: "term",
            queryLabel: "Spring",
        },
    };
    const secondHitMap = {
        "book::ch2": {
            chapterId: "book::ch2",
            currentHitScore: 3,
            queryType: "term",
            queryLabel: "JdbcTemplate",
        },
    };

    const firstHistory = updateSessionHitHistory({}, firstHitMap, 1000);
    const secondHistory = updateSessionHitHistory(firstHistory, secondHitMap, 2000);
    const mergedSecondMap = mergeAskHitWithSessionHistory(secondHitMap, secondHistory);

    assert.equal(mergedSecondMap["book::ch1"].currentHitScore, 0);
    assert.equal(mergedSecondMap["book::ch1"].sessionHitCount, 1);
    assert.equal(mergedSecondMap["book::ch1"].queryLabel, null);
    assert.equal(mergedSecondMap["book::ch2"].currentHitScore, 3);
    assert.equal(mergedSecondMap["book::ch2"].sessionHitCount, 2);
});
