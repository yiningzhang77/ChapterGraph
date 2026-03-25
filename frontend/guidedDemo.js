export const GUIDED_DEMO_MIN_STEP_PAUSE_MS = 3000;

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
        title: "欢迎体验 ChapterGraph",
        text: "这段回放会展示三件事：图谱如何围绕问题局部召回、系统如何拒绝过宽问题，以及推荐词如何让第二轮回答更聚焦。",
        actionText: "本步不会修改页面，先让你知道接下来会发生什么。",
    },
    expand_books: {
        title: "展开所有书",
        text: "先把所有书节点展开，让章节关系图完整显示出来。",
        actionText: "系统会自动展开全部书节点。",
    },
    term_mode: {
        title: "切到术语问答",
        text: "先进入术语问答模式，因为它最能展示召回效果和问题收窄机制。",
        actionText: "系统会自动切换到 Ask by Term。",
    },
    actuator_question: {
        title: "先问一个明确问题",
        text: "我们先用一个较明确的问题，看系统能否稳定回答并联动高亮相关章节。",
        actionText: "系统会自动填写 Actuator 示例问题并发送。",
    },
    actuator_result: {
        title: "观察图和回答联动",
        text: "注意左侧图上只高亮了少量相关章节，这说明系统不是整张图一起扩散，而是在做局部召回。",
        actionText: "这一步不再发送请求，只给你时间观察结果。",
    },
    broad_question: {
        title: "再问一个过宽问题",
        text: "接下来故意问一个范围太大的问题，重点不是看它直接答什么，而是看系统会不会先阻止泛化回答。",
        actionText: "系统会自动填写 Spring 的宽问题并发送。",
    },
    blocked_result: {
        title: "观察状态机与推荐词",
        text: "这里系统不会直接硬答，而是提示范围过宽，并给出更适合继续追问的推荐词。",
        actionText: "这一步不再发送请求，只让你看清状态机表现。",
    },
    narrowed_question: {
        title: "自动用推荐词继续第二轮",
        text: "现在系统会自动采用更聚焦的推荐词，再问一次同方向问题。",
        actionText: "系统会自动选择推荐词、填写第二轮问题并发送。",
    },
    finished: {
        title: "演示完成",
        text: "你已经看完主链路：明确问题可以稳定回答，宽问题会被阻断，推荐词会把第二轮问答收窄得更聚焦。",
        actionText: "页面保持当前状态，你可以继续自由探索。",
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

function isFinishedStep(stepId) {
    return stepId === GUIDED_DEMO_STEP_ORDER[GUIDED_DEMO_STEP_ORDER.length - 1];
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
    let readyForNext = false;
    let currentStepIndex = -1;

    const emitStatus = (partial) => {
        if (typeof onStatusChange === "function") {
            onStatusChange(partial);
        }
    };

    const updateStep = (stepId) => {
        if (typeof onStepChange === "function") {
            onStepChange(stepId);
        }
    };

    const syncStatus = (partial = {}) => {
        const stepId =
            currentStepIndex >= 0 && currentStepIndex < GUIDED_DEMO_STEP_ORDER.length
                ? GUIDED_DEMO_STEP_ORDER[currentStepIndex]
                : "intro";
        emitStatus({
            guidedDemoActive: active,
            guidedDemoRunning: running,
            guidedDemoReadyForNext: readyForNext,
            guidedDemoStep: stepId,
            guidedDemoStepIndex: Math.max(currentStepIndex, 0),
            ...partial,
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
                throw new Error("回放演示等待页面状态更新超时。");
            }
            await actions.sleep(pollMs);
        }
        throw new Error("回放演示已停止。");
    };

    const completeCurrentStep = async () => {
        await actions.sleep(GUIDED_DEMO_MIN_STEP_PAUSE_MS);
        if (!active) {
            throw new Error("回放演示已停止。");
        }
        running = false;
        readyForNext = !isFinishedStep(GUIDED_DEMO_STEP_ORDER[currentStepIndex]);
        syncStatus({
            guidedDemoPhase: isFinishedStep(GUIDED_DEMO_STEP_ORDER[currentStepIndex])
                ? "finished"
                : "ready",
        });
    };

    const executeCurrentStep = async () => {
        const stepId = GUIDED_DEMO_STEP_ORDER[currentStepIndex];
        running = true;
        readyForNext = false;
        updateStep(stepId);
        syncStatus({
            guidedDemoError: "",
            guidedDemoPhase: "running",
        });

        switch (stepId) {
            case "intro":
                break;
            case "expand_books":
                actions.expandAllBooks();
                break;
            case "term_mode":
                actions.setAskMode("term");
                break;
            case "actuator_question": {
                actions.setAskMode("term");
                actions.setAskTerm("Actuator");
                actions.setAskQuery("请用中文说明它是什么，它主要解决什么问题");
                await actions.sleep(180);
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
                break;
            }
            case "actuator_result":
                break;
            case "broad_question": {
                actions.setAskMode("term");
                actions.setAskTerm("Spring");
                actions.setAskQuery("How does Spring implement data persistence?");
                await actions.sleep(180);
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
                break;
            }
            case "blocked_result":
                break;
            case "narrowed_question": {
                const suggestedTerm = findPreferredSuggestedTerm(
                    latestAssistantMessage(getState().messages)?.suggestedTerms ?? [],
                );
                if (!suggestedTerm) {
                    throw new Error("回放演示没有找到可用的推荐词。");
                }
                actions.applySuggestedTerm(suggestedTerm);
                actions.setAskQuery("请继续用中文解释它在 Spring 里是怎么做的");
                await actions.sleep(180);
                const assistantCount = countAssistantMessages(getState().messages);
                await actions.submitAsk();
                await waitFor((snapshot) => {
                    if (snapshot.askLoading) return false;
                    return countAssistantMessages(snapshot.messages) > assistantCount;
                });
                break;
            }
            case "finished":
                break;
            default:
                throw new Error(`未知的回放演示步骤: ${stepId}`);
        }

        await completeCurrentStep();
    };

    const stop = () => {
        active = false;
        running = false;
        readyForNext = false;
        currentStepIndex = -1;
        emitStatus({
            guidedDemoActive: false,
            guidedDemoRunning: false,
            guidedDemoReadyForNext: false,
            guidedDemoPhase: "idle",
        });
    };

    const start = async () => {
        if (running) {
            return;
        }
        active = true;
        currentStepIndex = 0;
        try {
            await executeCurrentStep();
        } catch (error) {
            running = false;
            readyForNext = false;
            const message = error instanceof Error ? error.message : "回放演示执行失败。";
            if (message === "回放演示已停止。") {
                stop();
                return;
            }
            syncStatus({
                guidedDemoPhase: "error",
                guidedDemoError: message,
            });
            if (typeof onError === "function") {
                onError(message);
            }
        }
    };

    const next = async () => {
        if (!active || running || !readyForNext) {
            return;
        }
        if (currentStepIndex >= GUIDED_DEMO_STEP_ORDER.length - 1) {
            return;
        }
        currentStepIndex += 1;
        try {
            await executeCurrentStep();
        } catch (error) {
            running = false;
            readyForNext = false;
            const message = error instanceof Error ? error.message : "回放演示执行失败。";
            if (message === "回放演示已停止。") {
                stop();
                return;
            }
            syncStatus({
                guidedDemoPhase: "error",
                guidedDemoError: message,
            });
            if (typeof onError === "function") {
                onError(message);
            }
        }
    };

    return {
        start,
        next,
        stop,
        restart: async () => {
            stop();
            await start();
        },
        isActive: () => active,
        isRunning: () => running,
        isReadyForNext: () => readyForNext,
    };
}
