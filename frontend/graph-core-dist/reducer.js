function reducer(state, action) {
  switch (action.type) {
    case "LOAD_GRAPH_START":
      return { uiPhase: "loading" };
    case "LOAD_GRAPH_SUCCESS":
      return {
        graph: action.graph,
        expandedBooks: /* @__PURE__ */ new Set(),
        uiPhase: "ready"
      };
    case "SET_ASK_HIT_MAP":
      return { askHitMap: action.askHitMap ?? {} };
    case "TOGGLE_BOOK": {
      const nextExpanded = new Set(state.expandedBooks);
      if (nextExpanded.has(action.bookId)) {
        nextExpanded.delete(action.bookId);
      } else {
        nextExpanded.add(action.bookId);
      }
      return { expandedBooks: nextExpanded };
    }
    case "SET_HOVERED_NODE":
      return { hoveredNode: action.node };
    case "SET_TRANSFORM":
      return { transform: action.transform };
    case "SET_THEME":
      return { theme: action.theme };
    case "RESIZE":
      return { dimensions: { width: action.width, height: action.height } };
    default:
      console.warn("Unknown action", action);
      return {};
  }
}
export {
  reducer
};
