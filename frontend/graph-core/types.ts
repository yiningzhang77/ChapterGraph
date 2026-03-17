// UI phase
export type UIPhase = "idle" | "loading" | "ready";

export type GraphNode =
    | { id: string; type: "book"; size?: number }
    | { id: string; type: "chapter"; book_id: string; title?: string };

export type GraphEdge = {
    source: string;
    target: string;
    score: number;
    type?: string;
};

export type Graph = {
    nodes: GraphNode[];
    edges: GraphEdge[];
};

export type AskHitInfo = {
    chapterId: string;
    bookId: string | null;
    currentHitScore: number;
    isSeed: boolean;
    isClusterNode: boolean;
    evidenceSectionCount: number;
    evidenceBulletCount: number;
    queryType: string | null;
    queryLabel: string | null;
};

export type ViewNode = {
    id: string;
    type: "book" | "chapter";
    bookId: string;
    label: string;
    color: string;
    askHit: AskHitInfo | null;
    chapterId?: string;
    chapterCount?: number;
    x?: number | null;
    y?: number | null;
    fx?: number | null;
    fy?: number | null;
};

export type ViewLink = {
    source: string | ViewNode;
    target: string | ViewNode;
    score: number;
};

export type Transform = {
    x: number;
    y: number;
    k: number;
};

export type Dimensions = {
    width: number;
    height: number;
};

// Action types
export type Action =
    | { type: "LOAD_GRAPH_START" }
    | { type: "LOAD_GRAPH_SUCCESS"; graph: Graph }
    | { type: "SET_ASK_HIT_MAP"; askHitMap: Record<string, AskHitInfo> }
    | { type: "TOGGLE_BOOK"; bookId: string }
    | { type: "SET_HOVERED_NODE"; node: ViewNode | null }
    | { type: "SET_TRANSFORM"; transform: Transform }
    | { type: "SET_THEME"; theme: "light" | "dark" }
    | { type: "RESIZE"; width: number; height: number };

// Core state
export interface CoreState {
    uiPhase: UIPhase;
    graph: Graph | null;
    askHitMap: Record<string, AskHitInfo>;
    expandedBooks: Set<string>;
    dimensions: Dimensions;
    nodes: ViewNode[];
    links: ViewLink[];
    transform: Transform;
    hoveredNode: ViewNode | null;
    theme: "light" | "dark";
}
