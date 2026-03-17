const MAX_ASK_HIT_SCORE = 7;

export function buildAskHitMap(result, context = {}) {
    if (!result || typeof result !== "object") {
        return {};
    }

    const hitMap = {};
    const cluster = result.cluster && typeof result.cluster === "object"
        ? result.cluster
        : null;
    const evidence = result.evidence && typeof result.evidence === "object"
        ? result.evidence
        : null;
    const queryType = typeof context.queryType === "string" ? context.queryType : null;
    const queryLabel = typeof context.queryLabel === "string" ? context.queryLabel : null;

    const ensureEntry = (chapterId, bookId = null) => {
        if (typeof chapterId !== "string" || !chapterId) {
            return null;
        }
        if (!hitMap[chapterId]) {
            hitMap[chapterId] = {
                chapterId,
                bookId,
                currentHitScore: 0,
                isSeed: false,
                isClusterNode: false,
                evidenceSectionCount: 0,
                evidenceBulletCount: 0,
                queryType,
                queryLabel,
            };
        } else if (!hitMap[chapterId].bookId && bookId) {
            hitMap[chapterId].bookId = bookId;
        }
        return hitMap[chapterId];
    };

    const seed = cluster && typeof cluster.seed === "object" ? cluster.seed : null;
    const seedChapterIds = seed && Array.isArray(seed.seed_chapter_ids)
        ? seed.seed_chapter_ids
        : [];
    seedChapterIds.forEach((chapterId) => {
        const entry = ensureEntry(chapterId);
        if (!entry) return;
        entry.isSeed = true;
        entry.currentHitScore += 3;
    });

    const chapters = cluster && Array.isArray(cluster.chapters) ? cluster.chapters : [];
    chapters.forEach((chapter) => {
        if (!chapter || typeof chapter !== "object") return;
        const entry = ensureEntry(chapter.chapter_id, chapter.book_id ?? null);
        if (!entry) return;
        entry.isClusterNode = true;
        entry.currentHitScore += 1;
    });

    const sections = evidence && Array.isArray(evidence.sections) ? evidence.sections : [];
    sections.forEach((section) => {
        if (!section || typeof section !== "object") return;
        const entry = ensureEntry(section.chapter_id);
        if (!entry) return;
        entry.evidenceSectionCount += 1;
        entry.currentHitScore += 1;
    });

    const bullets = evidence && Array.isArray(evidence.bullets) ? evidence.bullets : [];
    bullets.forEach((bullet) => {
        if (!bullet || typeof bullet !== "object") return;
        const entry = ensureEntry(bullet.chapter_id);
        if (!entry) return;
        entry.evidenceBulletCount += 1;
        entry.currentHitScore += 1;
    });

    Object.values(hitMap).forEach((entry) => {
        entry.currentHitScore = Math.min(MAX_ASK_HIT_SCORE, entry.currentHitScore);
    });

    return hitMap;
}

export function updateSessionHitHistory(previousHistory, currentHitMap, timestamp = Date.now()) {
    const nextHistory = {
        ...(previousHistory && typeof previousHistory === "object" ? previousHistory : {}),
    };
    const entries = currentHitMap && typeof currentHitMap === "object"
        ? Object.entries(currentHitMap)
        : [];

    entries.forEach(([chapterId]) => {
        const currentEntry = nextHistory[chapterId];
        const sessionHitCount = currentEntry && typeof currentEntry === "object"
            && typeof currentEntry.sessionHitCount === "number"
            ? currentEntry.sessionHitCount
            : 0;
        nextHistory[chapterId] = {
            sessionHitCount: sessionHitCount + 1,
            lastHitAt: timestamp,
        };
    });

    return nextHistory;
}

export function mergeAskHitWithSessionHistory(currentHitMap, sessionHitHistory) {
    const mergedHitMap = {};
    const currentEntries = currentHitMap && typeof currentHitMap === "object"
        ? Object.entries(currentHitMap)
        : [];

    currentEntries.forEach(([chapterId, hitEntry]) => {
        if (!hitEntry || typeof hitEntry !== "object") {
            return;
        }
        const sessionEntry = sessionHitHistory && typeof sessionHitHistory === "object"
            ? sessionHitHistory[chapterId]
            : null;
        mergedHitMap[chapterId] = {
            ...hitEntry,
            sessionHitCount: sessionEntry && typeof sessionEntry === "object"
                && typeof sessionEntry.sessionHitCount === "number"
                ? sessionEntry.sessionHitCount
                : 0,
            lastHitAt: sessionEntry && typeof sessionEntry === "object"
                && typeof sessionEntry.lastHitAt === "number"
                ? sessionEntry.lastHitAt
                : null,
        };
    });

    return mergedHitMap;
}
