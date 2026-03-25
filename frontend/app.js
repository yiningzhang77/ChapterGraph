import React, { useEffect, useReducer, useRef, useState } from "https://esm.sh/react@18.2.0";
import ReactDOM from "https://esm.sh/react-dom@18.2.0/client";
import { marked } from "https://esm.sh/marked@15.0.12";
import DOMPurify from "https://esm.sh/dompurify@3.2.6";
import {
    rebuildGraph,
    draw,
    findNodeAtPosition,
} from "./graph-core-dist/buildView.js";
import {
    buildAskHitMap,
    mergeAskHitWithSessionHistory,
    updateSessionHitHistory,
} from "./askHitMap.js";
import {
    GUIDED_DEMO_MIN_STEP_PAUSE_MS,
    GUIDED_DEMO_STEP_DETAILS,
    GUIDED_DEMO_STEP_ORDER,
    createGuidedDemoController,
} from "./guidedDemo.js";
import { renderGuidedDemoOverlay } from "./guidedDemoOverlay.js";
import { reducer as coreReducer } from "./graph-core-dist/reducer.js";

function resolveApiBaseUrl() {
    const fromQuery = new URLSearchParams(window.location.search).get("api");
    if (fromQuery) {
        return fromQuery;
    }

    const runtimeConfig =
        window.CHAPTERGRAPH_CONFIG &&
        typeof window.CHAPTERGRAPH_CONFIG === "object"
            ? window.CHAPTERGRAPH_CONFIG
            : null;
    const fromRuntimeConfig =
        runtimeConfig && typeof runtimeConfig.apiBaseUrl === "string"
            ? runtimeConfig.apiBaseUrl.trim()
            : "";
    if (fromRuntimeConfig) {
        return fromRuntimeConfig;
    }

    return "http://127.0.0.1:8000";
}

const API = resolveApiBaseUrl();
const h = React.createElement;

marked.setOptions({
    gfm: true,
    breaks: true,
});

function renderMarkdownToHtml(markdownText) {
    if (typeof markdownText !== "string" || !markdownText.trim()) {
        return "";
    }
    return DOMPurify.sanitize(marked.parse(markdownText));
}

function createInitialState() {
    return {
        graph: null,
        askHitMap: {},
        expandedBooks: new Set(),
        nodes: [],
        links: [],
        transform: d3.zoomIdentity,
        hoveredNode: null,
        dimensions: { width: window.innerWidth, height: window.innerHeight },
        theme: "light",
        uiPhase: "idle",
    };
}

function App() {
    const [runs, setRuns] = useState([]);
    const [selectedRun, setSelectedRun] = useState("");
    const [askMode, setAskMode] = useState("term");
    const [askQuery, setAskQuery] = useState("");
    const [askTerm, setAskTerm] = useState("");
    const [narrowingHint, setNarrowingHint] = useState("");
    const [messages, setMessages] = useState([]);
    const [askError, setAskError] = useState("");
    const [askLoading, setAskLoading] = useState(false);
    const [selectedChapter, setSelectedChapter] = useState(null);
    const [sessionHitHistory, setSessionHitHistory] = useState({});
    const [guidedDemoActive, setGuidedDemoActive] = useState(false);
    const [guidedDemoLayoutActive, setGuidedDemoLayoutActive] = useState(false);
    const [guidedDemoRunning, setGuidedDemoRunning] = useState(false);
    const [guidedDemoReadyForNext, setGuidedDemoReadyForNext] = useState(false);
    const [guidedDemoStep, setGuidedDemoStep] = useState("intro");
    const [guidedDemoPhase, setGuidedDemoPhase] = useState("idle");
    const [guidedDemoStepIndex, setGuidedDemoStepIndex] = useState(0);
    const [guidedDemoError, setGuidedDemoError] = useState("");
    const [state, dispatch] = useReducer(
        (currentState, action) => {
            const partial = coreReducer(currentState, action);
            return { ...currentState, ...partial };
        },
        null,
        createInitialState,
    );
    const stateRef = useRef(state);
    const simulationRef = useRef(null);
    const canvasRef = useRef(null);
    const tooltipRef = useRef(null);
    const guidedDemoControllerRef = useRef(null);
    const appSnapshotRef = useRef(null);
    const submitAskRef = useRef(null);
    const applySuggestedTermRef = useRef(null);
    const askMessagesRef = useRef(null);

    useEffect(() => {
        stateRef.current = state;
    }, [state]);

    useEffect(() => {
        appSnapshotRef.current = {
            selectedRun,
            askMode,
            askTerm,
            askQuery,
            askLoading,
            messages,
            askHitMap: state.askHitMap,
            graph: state.graph,
            expandedBooks: state.expandedBooks,
            selectedChapter,
        };
    }, [
        selectedRun,
        askMode,
        askTerm,
        askQuery,
        askLoading,
        messages,
        state.askHitMap,
        state.graph,
        state.expandedBooks,
        selectedChapter,
    ]);

    useEffect(() => {
        const container = askMessagesRef.current;
        if (!container) {
            return;
        }
        container.scrollTop = container.scrollHeight;
    }, [messages.length]);

    useEffect(() => {
        document.documentElement.dataset.theme =
            state.theme === "dark" ? "dark" : "light";
    }, [state.theme]);

    useEffect(() => {
        if (!state.graph) return;
        rebuildGraph(state, simulationRef);
    }, [state.graph, state.expandedBooks, state.askHitMap, state.dimensions]);

    useEffect(() => {
        const handleResize = () => {
            dispatch({
                type: "RESIZE",
                width: window.innerWidth,
                height: window.innerHeight,
            });
        };
        handleResize();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    useEffect(() => {
        fetch(`${API}/runs`)
            .then((res) => res.json())
            .then((data) => {
                setRuns(data);
                if (data.length > 0) {
                    setSelectedRun(String(data[0].id));
                }
            })
            .catch((err) => {
                console.error(err);
                setRuns([]);
            });
    }, []);

    useEffect(() => {
        if (!selectedRun) return;
        dispatch({ type: "LOAD_GRAPH_START" });
        dispatch({ type: "SET_ASK_HIT_MAP", askHitMap: {} });
        setSessionHitHistory({});
        setSelectedChapter(null);
        fetch(`${API}/graph?run_id=${selectedRun}`)
            .then((res) => res.json())
            .then((data) => {
                dispatch({
                    type: "LOAD_GRAPH_SUCCESS",
                    graph: data,
                });
            })
            .catch(console.error);
    }, [selectedRun]);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        let frame = null;
        const render = () => {
            draw(stateRef.current, ctx);
            frame = requestAnimationFrame(render);
        };
        render();
        return () => {
            if (frame) cancelAnimationFrame(frame);
        };
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        const tooltip = tooltipRef.current;
        if (!canvas) return;

        const zoomBehavior = d3
            .zoom()
            .scaleExtent([0.2, 5])
            .filter((event) => event.type !== "dblclick")
            .on("zoom", (event) => {
                dispatch({
                    type: "SET_TRANSFORM",
                    transform: event.transform,
                });
            });

        d3.select(canvas).call(zoomBehavior);

        const handleMove = (event) => {
            const rect = canvas.getBoundingClientRect();
            const x = (event.clientX - rect.left - stateRef.current.transform.x) / stateRef.current.transform.k;
            const y = (event.clientY - rect.top - stateRef.current.transform.y) / stateRef.current.transform.k;
            const hit = findNodeAtPosition(stateRef.current, x, y);
            dispatch({ type: "SET_HOVERED_NODE", node: hit });
            canvas.style.cursor = hit ? "pointer" : "default";

            if (!tooltip) return;
            if (hit) {
                tooltip.style.opacity = "1";
                tooltip.style.left = `${event.clientX + 12}px`;
                tooltip.style.top = `${event.clientY + 12}px`;
                const typeLabel = hit.type === "book" ? "Book" : "Chapter";
                tooltip.innerHTML = `
                    <div style="font-weight:600;margin-bottom:4px;">${hit.label}</div>
                    <div style="opacity:0.75;">${typeLabel}</div>
                `;
                if (hit.type === "book") {
                    tooltip.innerHTML += `<div style="opacity:0.75;">Chapters: ${hit.chapterCount ?? 0}</div>`;
                } else if (hit.chapterId && hit.chapterId !== hit.label) {
                    tooltip.innerHTML += `<div style="opacity:0.75;">${hit.chapterId}</div>`;
                }
                const askHit = hit.askHit && typeof hit.askHit === "object" ? hit.askHit : null;
                if (askHit && hit.type === "chapter") {
                    const lastHitLabel = typeof askHit.lastHitAt === "number"
                        ? new Date(askHit.lastHitAt).toLocaleTimeString()
                        : null;
                    tooltip.innerHTML += `
                        <div style="margin-top:6px;border-top:1px solid rgba(148,163,184,0.28);padding-top:6px;">
                            <div style="opacity:0.75;">Current hit score: ${askHit.currentHitScore ?? 0}</div>
                            <div style="opacity:0.75;">Seed hit: ${askHit.isSeed ? "yes" : "no"}</div>
                            <div style="opacity:0.75;">Evidence sections: ${askHit.evidenceSectionCount ?? 0}</div>
                            <div style="opacity:0.75;">Evidence bullets: ${askHit.evidenceBulletCount ?? 0}</div>
                            <div style="opacity:0.75;">Session hits: ${askHit.sessionHitCount ?? 0}</div>
                        </div>
                    `;
                    if (lastHitLabel) {
                        tooltip.innerHTML += `<div style="opacity:0.75;">Last hit: ${lastHitLabel}</div>`;
                    }
                    if (typeof askHit.queryType === "string") {
                        tooltip.innerHTML += `<div style="opacity:0.75;">Query type: ${askHit.queryType}</div>`;
                    }
                    if (typeof askHit.queryLabel === "string" && askHit.queryLabel) {
                        tooltip.innerHTML += `<div style="opacity:0.75;">Query label: ${askHit.queryLabel}</div>`;
                    }
                }
            } else {
                tooltip.style.opacity = "0";
            }
        };

        const handleLeave = () => {
            dispatch({ type: "SET_HOVERED_NODE", node: null });
            canvas.style.cursor = "default";
            if (tooltip) {
                tooltip.style.opacity = "0";
            }
        };

        const handleDblClick = (event) => {
            const rect = canvas.getBoundingClientRect();
            const x = (event.clientX - rect.left - stateRef.current.transform.x) / stateRef.current.transform.k;
            const y = (event.clientY - rect.top - stateRef.current.transform.y) / stateRef.current.transform.k;
            const hit = findNodeAtPosition(stateRef.current, x, y);
            if (!hit) return;
            dispatch({
                type: "TOGGLE_BOOK",
                bookId: hit.bookId,
            });
        };

        const handleClick = (event) => {
            const rect = canvas.getBoundingClientRect();
            const x = (event.clientX - rect.left - stateRef.current.transform.x) / stateRef.current.transform.k;
            const y = (event.clientY - rect.top - stateRef.current.transform.y) / stateRef.current.transform.k;
            const hit = findNodeAtPosition(stateRef.current, x, y);
            if (!hit || hit.type !== "chapter" || !hit.chapterId) {
                return;
            }
            setSelectedChapter({
                chapterId: hit.chapterId,
                title: hit.label,
                bookId: hit.bookId,
            });
        };

        canvas.addEventListener("mousemove", handleMove);
        canvas.addEventListener("mouseleave", handleLeave);
        canvas.addEventListener("dblclick", handleDblClick);
        canvas.addEventListener("click", handleClick);

        return () => {
            d3.select(canvas).on(".zoom", null);
            canvas.removeEventListener("mousemove", handleMove);
            canvas.removeEventListener("mouseleave", handleLeave);
            canvas.removeEventListener("dblclick", handleDblClick);
            canvas.removeEventListener("click", handleClick);
        };
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = state.dimensions.width;
        canvas.height = state.dimensions.height;
    }, [state.dimensions]);

    const onThemeToggle = () => {
        dispatch({
            type: "SET_THEME",
            theme: state.theme === "dark" ? "light" : "dark",
        });
    };

    const parseAskError = async (response) => {
        let detail = `HTTP ${response.status}`;
        try {
            const body = await response.json();
            if (body && typeof body.detail === "string") {
                detail = body.detail;
            }
        } catch (error) {
            detail = `HTTP ${response.status}`;
        }
        return detail;
    };

    const askByTerm = async (term, userQuery) => {
        const response = await fetch(`${API}/ask`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                run_id: Number(selectedRun),
                query_type: "term",
                term,
                user_query: userQuery,
                llm_enabled: true,
                return_cluster: true,
                return_graph_fragment: false,
            }),
        });
        if (!response.ok) {
            throw new Error(await parseAskError(response));
        }
        return response.json();
    };

    const askByChapter = async (query, chapterId) => {
        const response = await fetch(`${API}/ask`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                run_id: Number(selectedRun),
                query_type: "chapter",
                query,
                chapter_id: chapterId,
                llm_enabled: true,
                return_cluster: true,
                return_graph_fragment: false,
            }),
        });
        if (!response.ok) {
            throw new Error(await parseAskError(response));
        }
        return response.json();
    };

    const extractRetrievalWarnings = (result) => {
        const meta = result && typeof result === "object" ? result.meta : null;
        if (!meta || typeof meta !== "object") {
            return null;
        }
        const warnings = meta.retrieval_warnings;
        if (!warnings || typeof warnings !== "object") {
            return null;
        }
        return warnings;
    };

    const onSuggestedTermClick = (termValue) => {
        setAskMode("term");
        setAskTerm(termValue);
        setAskError("");
        setNarrowingHint(`术语已切换为 ${termValue}。你可以直接继续发送当前问题。`);
    };

    const expandAllBooks = () => {
        const graph = stateRef.current.graph;
        if (!graph || !Array.isArray(graph.nodes)) {
            return;
        }
        const alreadyExpanded = stateRef.current.expandedBooks;
        graph.nodes
            .filter((node) => node && node.type === "book" && typeof node.id === "string")
            .forEach((bookNode) => {
                if (alreadyExpanded.has(bookNode.id)) {
                    return;
                }
                dispatch({
                    type: "TOGGLE_BOOK",
                    bookId: bookNode.id,
                });
            });
    };

    const submitAsk = async () => {
        const query = askQuery.trim();
        const term = askTerm.trim();
        if (!selectedRun) {
            setAskError("请先选择一个 run。");
            return;
        }
        if (askMode === "term" && !term) {
            setAskError("请输入一个术语。");
            return;
        }
        if (askMode === "chapter" && !selectedChapter?.chapterId) {
            setAskError("请先点击一个章节节点，再使用章节问答。");
            return;
        }

        const userMessage = {
            role: "user",
            text: askMode === "term"
                ? (query ? `${term}\n${query}` : term)
                : (query || `chapter ${selectedChapter.chapterId}`),
            queryType: askMode,
            term: askMode === "term" ? term : null,
            chapterId: askMode === "chapter" ? selectedChapter.chapterId : null,
        };
        setMessages((prev) => [...prev, userMessage]);
        setAskError("");
        setNarrowingHint("");
        setAskLoading(true);
        dispatch({ type: "SET_ASK_HIT_MAP", askHitMap: {} });

        try {
            const result = askMode === "chapter"
                ? await askByChapter(query, selectedChapter.chapterId)
                : await askByTerm(term, query);
            const currentAskHitMap = buildAskHitMap(result, {
                queryType: askMode,
                queryLabel: askMode === "term"
                    ? term
                    : selectedChapter?.chapterId ?? null,
            });
            setSessionHitHistory((previousHistory) =>
                {
                    const nextHistory = updateSessionHitHistory(previousHistory, currentAskHitMap);
                    dispatch({
                        type: "SET_ASK_HIT_MAP",
                        askHitMap: mergeAskHitWithSessionHistory(
                            currentAskHitMap,
                            nextHistory,
                        ),
                    });
                    return nextHistory;
                },
            );
            const meta = result && typeof result === "object" && result.meta && typeof result.meta === "object"
                ? result.meta
                : {};
            const responseState = typeof meta.response_state === "string" ? meta.response_state : null;
            const warnings = extractRetrievalWarnings(result);
            const warningMessage = warnings && typeof warnings.message === "string"
                ? warnings.message
                : "";
            const suggestedTerms = warnings && Array.isArray(warnings.suggested_terms)
                ? warnings.suggested_terms.filter((value) => typeof value === "string")
                : [];
            const llmError = meta && typeof meta.llm_error === "string"
                ? meta.llm_error
                : "";
            const answer = typeof result.answer_markdown === "string" && result.answer_markdown.trim()
                ? result.answer_markdown
                : llmError
                    ? `LLM request failed: ${llmError}`
                : responseState === "needs_narrower_term"
                    ? ""
                    : "No answer returned from /ask.";
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: answer,
                    queryType: result.query_type,
                    responseState,
                    warningMessage,
                    suggestedTerms,
                    chapterId: askMode === "chapter" ? selectedChapter.chapterId : null,
                },
            ]);
            setAskQuery("");
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to call /ask.";
            setAskError(message);
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    text: `Request failed: ${message}`,
                    queryType: askMode,
                    chapterId: askMode === "chapter" ? selectedChapter?.chapterId ?? null : null,
                },
            ]);
        } finally {
            setAskLoading(false);
        }
    };

    const onAskSubmit = async () => {
        await submitAsk();
    };
    submitAskRef.current = submitAsk;
    applySuggestedTermRef.current = onSuggestedTermClick;

    useEffect(() => {
        guidedDemoControllerRef.current = createGuidedDemoController({
            getState: () => appSnapshotRef.current ?? {
                messages: [],
                askLoading: false,
                askHitMap: {},
                graph: null,
                expandedBooks: new Set(),
            },
            actions: {
                sleep: (ms) => new Promise((resolve) => window.setTimeout(resolve, ms)),
                setAskMode: (mode) => setAskMode(mode),
                setAskTerm: (value) => setAskTerm(value),
                setAskQuery: (value) => setAskQuery(value),
                submitAsk: () => submitAskRef.current?.(),
                applySuggestedTerm: (value) => applySuggestedTermRef.current?.(value),
                expandAllBooks,
            },
            onStatusChange: (nextStatus) => {
                if (Object.prototype.hasOwnProperty.call(nextStatus, "guidedDemoActive")) {
                    const nextActive = Boolean(nextStatus.guidedDemoActive);
                    setGuidedDemoActive(nextActive);
                    setGuidedDemoLayoutActive(nextActive);
                }
                if (Object.prototype.hasOwnProperty.call(nextStatus, "guidedDemoRunning")) {
                    setGuidedDemoRunning(Boolean(nextStatus.guidedDemoRunning));
                }
                if (Object.prototype.hasOwnProperty.call(nextStatus, "guidedDemoReadyForNext")) {
                    setGuidedDemoReadyForNext(Boolean(nextStatus.guidedDemoReadyForNext));
                }
                if (typeof nextStatus.guidedDemoPhase === "string") {
                    setGuidedDemoPhase(nextStatus.guidedDemoPhase);
                }
                if (typeof nextStatus.guidedDemoStepIndex === "number") {
                    setGuidedDemoStepIndex(nextStatus.guidedDemoStepIndex);
                }
                if (typeof nextStatus.guidedDemoError === "string") {
                    setGuidedDemoError(nextStatus.guidedDemoError);
                }
            },
            onStepChange: (stepId) => {
                if (typeof stepId === "string") {
                    setGuidedDemoStep(stepId);
                    setGuidedDemoError("");
                }
            },
            onError: (message) => {
                setGuidedDemoError(message);
            },
        });
    }, []);

    const startGuidedDemo = async () => {
        setGuidedDemoError("");
        await guidedDemoControllerRef.current?.start();
    };

    const stopGuidedDemo = () => {
        guidedDemoControllerRef.current?.stop();
    };

    const restartGuidedDemo = async () => {
        setGuidedDemoError("");
        await guidedDemoControllerRef.current?.restart();
    };

    const nextGuidedDemoStep = async () => {
        await guidedDemoControllerRef.current?.next();
    };

    const askHeaderText = askMode === "chapter"
        ? "章节问答"
        : "术语问答";
    const guidedDemoStepDetails = GUIDED_DEMO_STEP_DETAILS[guidedDemoStep] ?? null;
    const currentGuidedDemoStepIndex = Math.max(0, guidedDemoStepIndex);
    const guidedDemoPauseSeconds = Math.round(GUIDED_DEMO_MIN_STEP_PAUSE_MS / 1000);

    return (
        h(React.Fragment, null,
            renderGuidedDemoOverlay(h, {
                active: guidedDemoActive,
                stepDetails: guidedDemoStepDetails,
                stepIndex: currentGuidedDemoStepIndex,
                totalSteps: GUIDED_DEMO_STEP_ORDER.length,
                isRunning: guidedDemoRunning,
                readyForNext: guidedDemoReadyForNext,
                phase: guidedDemoPhase,
                error: guidedDemoError,
                onNext: nextGuidedDemoStep,
                onStop: stopGuidedDemo,
                onRestart: restartGuidedDemo,
            }),
            h("div", { id: "topbar" },
                h(
                    "select",
                    {
                        value: selectedRun,
                        onChange: (e) => setSelectedRun(e.target.value),
                    },
                    runs.length === 0
                        ? h("option", { value: "" }, "failed to load runs")
                        : runs.map((run) =>
                            h(
                                "option",
                                { key: run.id, value: String(run.id) },
                                `run ${run.id} (${run.book_ids.join(", ")})`,
                            ),
                        ),
                ),
                h(
                    "button",
                    { id: "themeToggle", type: "button", onClick: onThemeToggle },
                    state.theme === "dark" ? "Theme: Dark" : "Theme: Light",
                ),
            ),
            h("canvas", { id: "graph", ref: canvasRef }),
            h("div", { id: "tooltip", ref: tooltipRef }),
            h("aside", {
                id: "askPanel",
                className: guidedDemoLayoutActive ? "demoLayout" : "",
            },
                h("div", { className: "askHeader" }, askHeaderText),
                h(
                    "button",
                    {
                        id: "guidedDemoTrigger",
                        type: "button",
                        className: guidedDemoActive ? "guidedDemoBtn running" : "guidedDemoBtn",
                        onClick: guidedDemoActive ? restartGuidedDemo : startGuidedDemo,
                    },
                    guidedDemoActive ? "重新开始回放" : "回放演示（逐步）",
                ),
                guidedDemoActive
                    ? h(
                        "div",
                        { className: "askHint" },
                        guidedDemoRunning
                            ? `当前步骤正在自动执行。每一步完成后会停顿约 ${guidedDemoPauseSeconds} 秒，再由你点击“下一步”继续。`
                            : "当前处于演示回放模式。你只需要点击顶部气泡里的“下一步”继续。",
                    )
                    : null,
                h("div", { className: "askModeRow" },
                    h(
                        "button",
                        {
                            "data-demo-role": "ask-mode-term",
                            type: "button",
                            className: askMode === "term" ? "askModeBtn active" : "askModeBtn",
                            onClick: () => setAskMode("term"),
                        },
                        "按术语提问",
                    ),
                    h(
                        "button",
                        {
                            "data-demo-role": "ask-mode-chapter",
                            type: "button",
                            className: askMode === "chapter" ? "askModeBtn active" : "askModeBtn",
                            onClick: () => setAskMode("chapter"),
                        },
                        "按章节提问",
                    ),
                ),
                askMode === "chapter"
                    ? h(
                        "div",
                        {
                            className: selectedChapter
                                ? "askSelectedChapter hint active"
                                : "askSelectedChapter hint",
                        },
                        selectedChapter
                            ? `已选章节：${selectedChapter.chapterId} (${selectedChapter.bookId})`
                            : "提示：请先在左侧图里点击一个章节节点。",
                    )
                    : null,
                askMode === "term"
                    ? h(React.Fragment, null,
                        h("div", { className: "askFieldLabel" }, "术语"),
                        h("input", {
                            id: "guidedDemoTermInput",
                            className: "askFieldInput",
                            type: "text",
                            placeholder: "Actuator / JdbcTemplate / data persistence",
                            value: askTerm,
                            onChange: (e) => setAskTerm(e.target.value),
                            disabled: askLoading,
                        }),
                    )
                    : null,
                h(
                    "div",
                    { className: "askFieldLabel" },
                    askMode === "chapter" ? "问题（可选）" : "围绕这个术语继续提问（可选）",
                ),
                h("textarea", {
                    id: "guidedDemoQueryInput",
                    className: "askInput",
                    placeholder: askMode === "chapter"
                        ? "继续追问这个章节..."
                        : "继续追问这个术语...",
                    value: askQuery,
                    onChange: (e) => setAskQuery(e.target.value),
                    disabled: askLoading,
                }),
                h(
                    "button",
                    {
                        id: "guidedDemoSubmit",
                        type: "button",
                        className: "askSubmit",
                        onClick: onAskSubmit,
                        disabled: askLoading,
                    },
                    askLoading ? "正在提问..." : "发送",
                ),
                askError ? h("div", { className: "askError" }, askError) : null,
                narrowingHint ? h("div", { className: "askHint" }, narrowingHint) : null,
                h(
                    "div",
                    { id: "guidedDemoMessages", className: "askMessages", ref: askMessagesRef },
                    messages.length === 0
                        ? h("div", { className: "askEmpty" }, "还没有消息。")
                        : messages.map((message, index) =>
                            h(
                                "div",
                                {
                                    key: `${message.role}-${index}`,
                                    className: message.role === "assistant" ? "askMsg assistant" : "askMsg user",
                                },
                                h(
                                    "div",
                                    { className: "askMeta" },
                                    message.role === "assistant"
                                        ? "系统回答"
                                        : message.queryType === "chapter"
                                            ? `章节 ${message.chapterId ?? ""}`.trim()
                                            : `术语 ${message.term ?? ""}`.trim(),
                                ),
                                message.role === "assistant"
                                    && message.warningMessage
                                    ? h(
                                        "div",
                                        {
                                            className: message.responseState === "broad_overview"
                                                ? "askWarning askWarningOverview"
                                                : "askWarning askWarningBlocked",
                                        },
                                        message.warningMessage,
                                    )
                                    : null,
                                message.role === "assistant"
                                    && message.warningMessage
                                    && Array.isArray(message.suggestedTerms)
                                    && message.suggestedTerms.length > 0
                                    ? h(
                                        "div",
                                        {
                                            className: "askSuggestions",
                                            "data-demo-role": "suggestions",
                                        },
                                        h("div", { className: "askSuggestionsLabel" }, "推荐继续追问："),
                                        h(
                                            "div",
                                            { className: "askSuggestionList" },
                                            ...message.suggestedTerms.map((termValue, termIndex) =>
                                                h(
                                                    "button",
                                                    {
                                                        key: `suggestion-${index}-${termIndex}`,
                                                        className: "askSuggestionChip",
                                                        type: "button",
                                                        onClick: () => onSuggestedTermClick(termValue),
                                                    },
                                                    termValue,
                                                ),
                                            ),
                                        ),
                                    )
                                    : null,
                                message.text
                                    ? message.role === "assistant"
                                        ? h("div", {
                                            className: "askText markdown",
                                            dangerouslySetInnerHTML: {
                                                __html: renderMarkdownToHtml(message.text),
                                            },
                                        })
                                        : h("div", { className: "askText userText" }, message.text)
                                    : null,
                            ),
                        ),
                ),
            ),
        )
    );
}

const root = ReactDOM.createRoot(document.getElementById("app"));
root.render(React.createElement(App));
