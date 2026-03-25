export const GUIDED_DEMO_STEP_ORDER = [
    "intro",
    "expand_books",
    "term_mode",
    "actuator_question",
    "actuator_result",
    "broad_question",
    "blocked_result",
    "narrowed_question",
    "finished",
];

export const GUIDED_DEMO_STEP_DETAILS = {
    intro: {
        title: "Welcome",
        text: "This demo will show graph recall, answer-to-graph linkage, and how broad questions are narrowed before the system answers.",
    },
    expand_books: {
        title: "Expand the graph",
        text: "Expand all books first so the chapter graph is fully visible.",
    },
    term_mode: {
        title: "Use term mode",
        text: "We start with Ask by Term because it best shows retrieval quality and narrowing behavior.",
    },
    actuator_question: {
        title: "First question",
        text: "Use a precise term question first so the system can show a normal, grounded answer.",
    },
    actuator_result: {
        title: "Observe the graph",
        text: "Notice that only a focused subset of chapters lights up. The system is not expanding across the whole graph.",
    },
    broad_question: {
        title: "Now try a broad question",
        text: "We intentionally ask something too wide to show that the system does not hard-answer vague requests.",
    },
    blocked_result: {
        title: "Narrowing suggestions",
        text: "The system blocks the broad question and offers better next-step terms.",
    },
    narrowed_question: {
        title: "Second-round question",
        text: "Use the suggested term to ask again and observe that the answer becomes more focused.",
    },
    finished: {
        title: "Demo complete",
        text: "You have seen the main runtime loop: focused retrieval, graph highlighting, broad-query blocking, and narrowing-driven retry.",
    },
};

export function getAllBookIds(graph) {
    if (!graph || !Array.isArray(graph.nodes)) {
        return [];
    }
    return graph.nodes
        .filter((node) => node && node.type === "book" && typeof node.id === "string")
        .map((node) => node.id);
}

export function findPreferredSuggestedTerm(suggestedTerms) {
    if (!Array.isArray(suggestedTerms) || suggestedTerms.length === 0) {
        return null;
    }
    const preferredTerms = ["data persistence", "JdbcTemplate", "Spring Data JPA"];
    const normalized = suggestedTerms
        .filter((term) => typeof term === "string" && term.trim())
        .map((term) => term.trim());
    for (const preferredTerm of preferredTerms) {
        const match = normalized.find(
            (term) => term.toLowerCase() === preferredTerm.toLowerCase(),
        );
        if (match) return match;
    }
    return normalized[0] ?? null;
}

export function countAssistantMessages(messages) {
    if (!Array.isArray(messages)) {
        return 0;
    }
    return messages.filter(
        (message) => message && typeof message === "object" && message.role === "assistant",
    ).length;
}

export function latestAssistantMessage(messages) {
    if (!Array.isArray(messages)) {
        return null;
    }
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const message = messages[index];
        if (message && typeof message === "object" && message.role === "assistant") {
            return message;
        }
    }
    return null;
}

export function createGuidedDemoController({
    getState,
    actions,
    onStatusChange,
    onStepChange,
    onError,
}) {
    let active = false;
    let running = false;

    const setStatus = (partial) => {
        if (typeof onStatusChange === "function") {
            onStatusChange(partial);
        }
    };

    const setStep = (stepId) => {
        if (typeof onStepChange === "function") {
            onStepChange(stepId);
        }
        setStatus({ guidedDemoStep: stepId });
    };

    const stop = () => {
        active = false;
        running = false;
        setStatus({
            guidedDemoActive: false,
            guidedDemoRunning: false,
        });
    };

    const waitFor = async (predicate, timeoutMs = 45_000, pollMs = 150) => {
        const startedAt = Date.now();
        while (active) {
            const snapshot = getState();
            if (predicate(snapshot)) {
                return snapshot;
            }
            if (Date.now() - startedAt >= timeoutMs) {
                throw new Error("Guided Demo timed out while waiting for the page state to update.");
            }
            await actions.sleep(pollMs);
        }
        throw new Error("Guided Demo was stopped.");
    };

    const run = async () => {
        if (running) return;
        active = true;
        running = true;
        setStatus({
            guidedDemoActive: true,
            guidedDemoRunning: true,
            guidedDemoError: "",
        });

        try {
            setStep("intro");
            await actions.sleep(400);

            setStep("expand_books");
            actions.expandAllBooks();
            await actions.sleep(500);

            setStep("term_mode");
            actions.setAskMode("term");
            await actions.sleep(150);

            setStep("actuator_question");
            actions.setAskTerm("Actuator");
            actions.setAskQuery("请用中文说明它是什么，它主要解决什么问题");
            await actions.sleep(150);
            {
                const assistantCount = countAssistantMessages(getState().messages);
                await actions.submitAsk();
                await waitFor((snapshot) => {
                    if (snapshot.askLoading) return false;
                    return countAssistantMessages(snapshot.messages) > assistantCount;
                });
                await waitFor(
                    (snapshot) => Object.keys(snapshot.askHitMap ?? {}).length > 0,
                    20_000,
                );
            }

            setStep("actuator_result");
            await actions.sleep(1200);

            setStep("broad_question");
            actions.setAskMode("term");
            actions.setAskTerm("Spring");
            actions.setAskQuery("How does Spring implement data persistence?");
            await actions.sleep(150);
            {
                const assistantCount = countAssistantMessages(getState().messages);
                await actions.submitAsk();
                await waitFor((snapshot) => {
                    if (snapshot.askLoading) return false;
                    if (countAssistantMessages(snapshot.messages) <= assistantCount) {
                        return false;
                    }
                    const latestMessage = latestAssistantMessage(snapshot.messages);
                    return !!(
                        latestMessage
                        && latestMessage.responseState === "needs_narrower_term"
                        && Array.isArray(latestMessage.suggestedTerms)
                        && latestMessage.suggestedTerms.length > 0
                    );
                });
            }

            setStep("blocked_result");
            await actions.sleep(1200);

            const suggestedTerm = findPreferredSuggestedTerm(
                latestAssistantMessage(getState().messages)?.suggestedTerms ?? [],
            );
            if (!suggestedTerm) {
                throw new Error("Guided Demo could not find a usable narrowing suggestion.");
            }

            setStep("narrowed_question");
            actions.applySuggestedTerm(suggestedTerm);
            actions.setAskQuery("请继续用中文解释它在 Spring 里是怎么做的");
            await actions.sleep(150);
            {
                const assistantCount = countAssistantMessages(getState().messages);
                await actions.submitAsk();
                await waitFor((snapshot) => {
                    if (snapshot.askLoading) return false;
                    return countAssistantMessages(snapshot.messages) > assistantCount;
                });
            }

            setStep("finished");
            setStatus({
                guidedDemoActive: true,
                guidedDemoRunning: false,
            });
            running = false;
        } catch (error) {
            running = false;
            const message = error instanceof Error ? error.message : "Guided Demo failed.";
            if (message === "Guided Demo was stopped.") {
                stop();
                return;
            }
            setStatus({
                guidedDemoActive: true,
                guidedDemoRunning: false,
                guidedDemoError: message,
            });
            if (typeof onError === "function") {
                onError(message);
            }
        }
    };

    return {
        start: run,
        stop,
        isActive: () => active,
        isRunning: () => running,
    };
}
