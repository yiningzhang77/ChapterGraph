import React, { useEffect, useReducer, useRef, useState } from "https://esm.sh/react@18.2.0";
import ReactDOM from "https://esm.sh/react-dom@18.2.0/client";
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
    GUIDED_DEMO_STEP_DETAILS,
    GUIDED_DEMO_STEP_ORDER,
    createGuidedDemoController,
} from "./guidedDemo.js";
import { createGuidedDemoTour } from "./guidedDemoTour.js";
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
    const [guidedDemoRunning, setGuidedDemoRunning] = useState(false);
    const [guidedDemoStep, setGuidedDemoStep] = useState("intro");
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
    const guidedDemoTourRef = useRef(null);
    const appSnapshotRef = useRef(null);
    const submitAskRef = useRef(null);
    const applySuggestedTermRef = useRef(null);

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
        setNarrowingHint(`Term updated to ${termValue}. Review the question and send again.`);
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
            setAskError("Please select a run first.");
            return;
        }
        if (askMode === "term" && !term) {
            setAskError("Please enter a term.");
            return;
        }
        if (askMode === "chapter" && !selectedChapter?.chapterId) {
            setAskError("Please click a chapter node before chapter ask.");
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
                    setGuidedDemoActive(Boolean(nextStatus.guidedDemoActive));
                }
                if (Object.prototype.hasOwnProperty.call(nextStatus, "guidedDemoRunning")) {
                    setGuidedDemoRunning(Boolean(nextStatus.guidedDemoRunning));
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

    useEffect(() => {
        if (!guidedDemoActive) {
            guidedDemoTourRef.current?.cancel();
            guidedDemoTourRef.current = null;
            return;
        }

        const tour = createGuidedDemoTour({
            onCancel: () => {
                guidedDemoControllerRef.current?.stop();
            },
        });
        guidedDemoTourRef.current = tour;
        tour.start(guidedDemoStep);

        return () => {
            guidedDemoTourRef.current?.cancel();
            guidedDemoTourRef.current = null;
        };
    }, [guidedDemoActive]);

    useEffect(() => {
        if (!guidedDemoActive || !guidedDemoTourRef.current) {
            return;
        }
        guidedDemoTourRef.current.show(guidedDemoStep);
    }, [guidedDemoActive, guidedDemoStep]);

    const startGuidedDemo = async () => {
        setGuidedDemoError("");
        await guidedDemoControllerRef.current?.start();
    };

    const stopGuidedDemo = () => {
        guidedDemoControllerRef.current?.stop();
    };

    const askHeaderText = askMode === "chapter"
        ? "Chapter Ask"
        : "Term Ask";
    const guidedDemoStepDetails = GUIDED_DEMO_STEP_DETAILS[guidedDemoStep] ?? null;
    const guidedDemoStepIndex = Math.max(0, GUIDED_DEMO_STEP_ORDER.indexOf(guidedDemoStep));

    return (
        h(React.Fragment, null,
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
            h("aside", { id: "askPanel" },
                h("div", { className: "askHeader" }, askHeaderText),
                h(
                    "button",
                    {
                        id: "guidedDemoTrigger",
                        type: "button",
                        className: guidedDemoRunning ? "guidedDemoBtn running" : "guidedDemoBtn",
                        onClick: guidedDemoRunning ? stopGuidedDemo : startGuidedDemo,
                    },
                    guidedDemoRunning
                        ? "Stop Guided Demo"
                        : guidedDemoActive
                            ? "Restart Guided Demo"
                            : "✨ Guided Demo",
                ),
                guidedDemoActive
                    ? h(
                        "div",
                        {
                            className: guidedDemoError
                                ? "guidedDemoStatus guidedDemoStatusError"
                                : "guidedDemoStatus",
                        },
                        h(
                            "div",
                            { className: "guidedDemoStatusTitle" },
                            guidedDemoStepDetails?.title
                                ? `Guided Demo · ${guidedDemoStepDetails.title}`
                                : "Guided Demo",
                        ),
                        h(
                            "div",
                            null,
                            `Step ${guidedDemoStepIndex + 1} / ${GUIDED_DEMO_STEP_ORDER.length}`,
                        ),
                        guidedDemoError
                            ? h("div", null, guidedDemoError)
                            : h(
                                "div",
                                null,
                                guidedDemoStepDetails?.text ?? "Running guided demo...",
                            ),
                        h(
                            "div",
                            { className: "guidedDemoStatusActions" },
                            h(
                                "button",
                                {
                                    type: "button",
                                    className: "guidedDemoStatusBtn",
                                    onClick: stopGuidedDemo,
                                },
                                "Stop",
                            ),
                            !guidedDemoRunning
                                ? h(
                                    "button",
                                    {
                                        type: "button",
                                        className: "guidedDemoStatusBtn",
                                        onClick: startGuidedDemo,
                                    },
                                    guidedDemoError ? "Retry" : "Restart",
                                )
                                : null,
                        ),
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
                        "Ask by Term",
                    ),
                    h(
                        "button",
                        {
                            "data-demo-role": "ask-mode-chapter",
                            type: "button",
                            className: askMode === "chapter" ? "askModeBtn active" : "askModeBtn",
                            onClick: () => setAskMode("chapter"),
                        },
                        "Ask by Chapter",
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
                            ? `Selected chapter: ${selectedChapter.chapterId} (${selectedChapter.bookId})`
                            : "Hint: click a chapter node on the graph first.",
                    )
                    : null,
                askMode === "term"
                    ? h(React.Fragment, null,
                        h("div", { className: "askFieldLabel" }, "Term"),
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
                    askMode === "chapter" ? "Question (Optional)" : "Ask About This Term (Optional)",
                ),
                h("textarea", {
                    id: "guidedDemoQueryInput",
                    className: "askInput",
                    placeholder: askMode === "chapter"
                        ? "Ask about the selected chapter..."
                        : "Ask a specific question about this term...",
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
                    askLoading ? "Asking..." : "Send",
                ),
                askError ? h("div", { className: "askError" }, askError) : null,
                narrowingHint ? h("div", { className: "askHint" }, narrowingHint) : null,
                h(
                    "div",
                    { id: "guidedDemoMessages", className: "askMessages" },
                    messages.length === 0
                        ? h("div", { className: "askEmpty" }, "No messages yet.")
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
                                        ? "assistant"
                                        : message.queryType === "chapter"
                                            ? `chapter ${message.chapterId ?? ""}`.trim()
                                            : `term ${message.term ?? ""}`.trim(),
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
                                        h("div", { className: "askSuggestionsLabel" }, "Try:"),
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
                                    ? h("div", { className: "askText" }, message.text)
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
