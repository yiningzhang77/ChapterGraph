import test from "node:test";
import assert from "node:assert/strict";

import {
    createGuidedDemoController,
    findPreferredSuggestedTerm,
    getAllBookIds,
} from "./guidedDemo.js";

test("getAllBookIds returns every book node id", () => {
    const graph = {
        nodes: [
            { id: "book-a", type: "book" },
            { id: "book-a::ch1", type: "chapter", book_id: "book-a" },
            { id: "book-b", type: "book" },
        ],
    };

    assert.deepEqual(getAllBookIds(graph), ["book-a", "book-b"]);
});

test("findPreferredSuggestedTerm prefers data persistence style narrowing", () => {
    assert.equal(
        findPreferredSuggestedTerm(["Spring Data", "data persistence", "JdbcTemplate"]),
        "data persistence",
    );
    assert.equal(
        findPreferredSuggestedTerm(["Spring Data", "Other Term"]),
        "Spring Data",
    );
    assert.equal(findPreferredSuggestedTerm([]), null);
});

test("guided demo controller advances step by step instead of auto-running everything", async () => {
    const state = {
        askMode: "term",
        askTerm: "",
        askQuery: "",
        askLoading: false,
        messages: [],
        askHitMap: {},
        graph: {
            nodes: [
                { id: "book-a", type: "book" },
                { id: "book-b", type: "book" },
            ],
        },
        expandedBooks: new Set(),
    };
    const actionLog = [];
    const statusLog = [];

    const controller = createGuidedDemoController({
        getState: () => state,
        actions: {
            sleep: async () => {},
            expandAllBooks: () => {
                state.expandedBooks = new Set(["book-a", "book-b"]);
                actionLog.push("expandAllBooks");
            },
            setAskMode: (value) => {
                state.askMode = value;
                actionLog.push(`setAskMode:${value}`);
            },
            setAskTerm: (value) => {
                state.askTerm = value;
                actionLog.push(`setAskTerm:${value}`);
            },
            setAskQuery: (value) => {
                state.askQuery = value;
                actionLog.push(`setAskQuery:${value}`);
            },
            applySuggestedTerm: (value) => {
                state.askTerm = value;
                actionLog.push(`applySuggestedTerm:${value}`);
            },
            submitAsk: async () => {
                actionLog.push(`submitAsk:${state.askTerm}`);
                state.askLoading = true;
                if (state.askTerm === "Actuator") {
                    state.messages.push({ role: "assistant", text: "Actuator answer" });
                    state.askHitMap = { "book-a::ch1": { chapterId: "book-a::ch1" } };
                } else if (state.askTerm === "Spring") {
                    state.messages.push({
                        role: "assistant",
                        text: "",
                        responseState: "needs_narrower_term",
                        suggestedTerms: ["Spring Data", "data persistence"],
                    });
                } else {
                    state.messages.push({ role: "assistant", text: "Focused answer" });
                }
                state.askLoading = false;
            },
        },
        onStatusChange: (status) => {
            statusLog.push({
                running: status.guidedDemoRunning,
                ready: status.guidedDemoReadyForNext,
                phase: status.guidedDemoPhase,
                stepIndex: status.guidedDemoStepIndex,
            });
        },
        onStepChange: () => {},
        onError: (message) => {
            throw new Error(message);
        },
    });

    await controller.start();

    assert.deepEqual(actionLog, []);
    assert.equal(controller.isReadyForNext(), true);

    await controller.next();
    await controller.next();
    await controller.next();
    await controller.next();
    await controller.next();
    await controller.next();
    await controller.next();
    await controller.next();

    assert.deepEqual(actionLog, [
        "expandAllBooks",
        "setAskMode:term",
        "setAskMode:term",
        "setAskTerm:Actuator",
        "setAskQuery:请用中文说明它是什么，它主要解决什么问题",
        "submitAsk:Actuator",
        "setAskMode:term",
        "setAskTerm:Spring",
        "setAskQuery:How does Spring implement data persistence?",
        "submitAsk:Spring",
        "applySuggestedTerm:data persistence",
        "setAskQuery:请继续用中文解释它在 Spring 里是怎么做的",
        "submitAsk:data persistence",
    ]);
    assert.equal(controller.isReadyForNext(), false);
    assert.ok(statusLog.some((entry) => entry.phase === "ready"));
    assert.ok(statusLog.some((entry) => entry.phase === "finished"));
});
