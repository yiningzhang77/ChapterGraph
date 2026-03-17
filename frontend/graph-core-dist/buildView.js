const BOOK_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"];
function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
function hexToRgb(hex) {
  const normalized = typeof hex === "string" ? hex.trim().replace("#", "") : "";
  if (normalized.length !== 6)
    return null;
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  if (Number.isNaN(red) || Number.isNaN(green) || Number.isNaN(blue))
    return null;
  return { red, green, blue };
}
function rgba(hex, alpha) {
  const rgb = hexToRgb(hex);
  if (!rgb)
    return hex;
  return `rgba(${rgb.red}, ${rgb.green}, ${rgb.blue}, ${clamp(alpha, 0, 1)})`;
}
function mixWithWhite(hex, amount) {
  const rgb = hexToRgb(hex);
  if (!rgb)
    return hex;
  const factor = clamp(amount, 0, 1);
  const red = Math.round(rgb.red + (255 - rgb.red) * factor);
  const green = Math.round(rgb.green + (255 - rgb.green) * factor);
  const blue = Math.round(rgb.blue + (255 - rgb.blue) * factor);
  return `rgb(${red}, ${green}, ${blue})`;
}
function getAskHitVisuals(node) {
  const askHit = node.askHit;
  const score = askHit?.currentHitScore ?? 0;
  const sessionHitCount = askHit?.sessionHitCount ?? 0;
  const hasCurrentHit = score > 0;
  const hasSessionHeat = sessionHitCount > 0;
  if (!hasCurrentHit && !hasSessionHeat)
    return null;
  const level = score >= 5 ? "strong" : score >= 3 ? "medium" : "light";
  const fillBoost = hasCurrentHit ? level === "strong" ? 0.35 : level === "medium" ? 0.2 : 0.1 : 0;
  const auraAlpha = hasCurrentHit ? level === "strong" ? 0.34 : level === "medium" ? 0.22 : 0.14 : 0;
  const auraRadius = hasCurrentHit ? level === "strong" ? 7 : level === "medium" ? 5 : 3 : 0;
  const sessionAuraWidth = Math.min(5, sessionHitCount);
  return {
    hasCurrentHit,
    level,
    fillColor: hasCurrentHit ? mixWithWhite(node.color, fillBoost) : node.color,
    auraColor: hasCurrentHit ? rgba(node.color, auraAlpha) : null,
    auraRadius,
    ringWidth: hasCurrentHit ? askHit?.isSeed ? 2.5 : 1.5 : 0,
    hasSessionHeat,
    sessionHitCount,
    sessionRingWidth: hasSessionHeat ? 1 + sessionAuraWidth * 0.35 : 0,
    sessionRingRadius: hasSessionHeat ? Math.max(auraRadius, 2) + 4 + sessionAuraWidth : 0,
    sessionRingColor: hasSessionHeat ? rgba("#f8fafc", 0.18 + Math.min(0.25, sessionHitCount * 0.04)) : null
  };
}
function getBookRadius(node) {
  const count = node.chapterCount ?? 1;
  return 12 + Math.sqrt(Math.max(count, 1)) * 2.2;
}
function getNodeRadius(node) {
  return node.type === "book" ? getBookRadius(node) : 5.5;
}
function findNodeAtPosition(state, x, y) {
  for (let i = state.nodes.length - 1; i >= 0; i -= 1) {
    const n = state.nodes[i];
    if (n.x == null || n.y == null)
      continue;
    const r = getNodeRadius(n);
    const dx = x - n.x;
    const dy = y - n.y;
    if (dx * dx + dy * dy <= r * r)
      return n;
  }
  return null;
}
function buildView(state, previousNodes) {
  if (!state.graph) {
    return { nodes: [], links: [] };
  }
  const askHitMap = state.askHitMap ?? {};
  const books = state.graph.nodes.filter((n) => n.type === "book");
  const chapters = state.graph.nodes.filter((n) => n.type === "chapter");
  const chapterCountMap = /* @__PURE__ */ new Map();
  chapters.forEach((c) => {
    chapterCountMap.set(
      c.book_id,
      (chapterCountMap.get(c.book_id) ?? 0) + 1
    );
  });
  const bookColorMap = /* @__PURE__ */ new Map();
  books.forEach((b, i) => {
    bookColorMap.set(b.id, BOOK_COLORS[i % BOOK_COLORS.length]);
  });
  const prevPositions = /* @__PURE__ */ new Map();
  previousNodes.forEach((n) => {
    if (n.x != null && n.y != null) {
      prevPositions.set(n.id, { x: n.x, y: n.y, fx: n.fx, fy: n.fy });
    }
  });
  const chapterCentroids = /* @__PURE__ */ new Map();
  previousNodes.forEach((n) => {
    if (n.type !== "chapter" || n.x == null || n.y == null)
      return;
    const current = chapterCentroids.get(n.bookId) ?? { x: 0, y: 0, count: 0 };
    chapterCentroids.set(n.bookId, {
      x: current.x + n.x,
      y: current.y + n.y,
      count: current.count + 1
    });
  });
  const nextNodes = [];
  const nextLinks = [];
  const visibleChapterIds = /* @__PURE__ */ new Set();
  books.forEach((book) => {
    const color = bookColorMap.get(book.id);
    const bookKey = `book-${book.id}`;
    if (state.expandedBooks.has(book.id)) {
      const base = prevPositions.get(bookKey);
      const centroid = chapterCentroids.get(book.id);
      const bx = base?.x ?? (centroid ? centroid.x / centroid.count : state.dimensions.width / 2);
      const by = base?.y ?? (centroid ? centroid.y / centroid.count : state.dimensions.height / 2);
      const bookChapters = chapters.filter((c) => c.book_id === book.id);
      bookChapters.forEach((c, i) => {
        const id = `chapter-${c.id}`;
        const prev = prevPositions.get(id);
        const angle = i * 0.55;
        const radius = 10 + i * 3.2;
        nextNodes.push({
          id,
          type: "chapter",
          bookId: book.id,
          label: c.title ? `${c.title}` : c.id,
          chapterId: c.id,
          askHit: askHitMap[c.id] ?? null,
          color,
          x: prev?.x ?? bx + Math.cos(angle) * radius,
          y: prev?.y ?? by + Math.sin(angle) * radius,
          fx: prev?.fx,
          fy: prev?.fy
        });
        visibleChapterIds.add(id);
      });
    } else {
      const prev = prevPositions.get(bookKey);
      nextNodes.push({
        id: bookKey,
        type: "book",
        bookId: book.id,
        label: book.id,
        askHit: null,
        color,
        chapterCount: chapterCountMap.get(book.id) ?? book.size,
        x: prev?.x,
        y: prev?.y,
        fx: prev?.fx,
        fy: prev?.fy
      });
    }
  });
  state.graph.edges.forEach((e) => {
    const s = `chapter-${e.source}`;
    const t = `chapter-${e.target}`;
    if (visibleChapterIds.has(s) && visibleChapterIds.has(t)) {
      nextLinks.push({ source: s, target: t, score: e.score });
    }
  });
  return { nodes: nextNodes, links: nextLinks };
}
function rebuildGraph(state, simulationRef) {
  if (!state.graph)
    return;
  const view = buildView(state, state.nodes);
  state.nodes = view.nodes;
  state.links = view.links;
  if (simulationRef.current)
    simulationRef.current.stop();
  simulationRef.current = d3.forceSimulation(state.nodes).force(
    "link",
    d3.forceLink(state.links).id((d) => d.id).strength((d) => Math.min(0.2, d.score)).distance((d) => 20 + (1 - d.score) * 60)
  ).force("charge", d3.forceManyBody().strength(-30)).force(
    "center",
    d3.forceCenter(state.dimensions.width / 2, state.dimensions.height / 2)
  );
}
function draw(state, ctx) {
  if (!ctx)
    return;
  const { nodes, links, transform, hoveredNode, dimensions } = state;
  const t = transform;
  const styles = getComputedStyle(document.documentElement);
  const edgeBase = styles.getPropertyValue("--edge").trim() || "rgba(100,116,139,0.22)";
  const textColor = styles.getPropertyValue("--text").trim() || "#0f172a";
  ctx.save();
  ctx.clearRect(0, 0, dimensions.width, dimensions.height);
  ctx.translate(t.x, t.y);
  ctx.scale(t.k, t.k);
  links.forEach((l) => {
    const s = typeof l.source === "string" ? nodes.find((n) => n.id === l.source) : l.source;
    const tg = typeof l.target === "string" ? nodes.find((n) => n.id === l.target) : l.target;
    if (!s || !tg || s.x == null || s.y == null || tg.x == null || tg.y == null)
      return;
    ctx.strokeStyle = edgeBase.replace(/[\d.]+\)$/g, `${0.1 + l.score * 0.8})`);
    ctx.lineWidth = 0.5 + l.score * 2;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(tg.x, tg.y);
    ctx.stroke();
  });
  nodes.forEach((n) => {
    if (n.x == null || n.y == null)
      return;
    const radius = getNodeRadius(n);
    const hitVisuals = n.type === "chapter" ? getAskHitVisuals(n) : null;
    if (hitVisuals) {
      if (hitVisuals.auraColor && hitVisuals.auraRadius > 0) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + hitVisuals.auraRadius, 0, Math.PI * 2);
        ctx.fillStyle = hitVisuals.auraColor;
        ctx.fill();
      }
      if (hitVisuals.hasSessionHeat && hitVisuals.sessionRingColor) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + hitVisuals.sessionRingRadius, 0, Math.PI * 2);
        ctx.strokeStyle = hitVisuals.sessionRingColor;
        ctx.lineWidth = hitVisuals.sessionRingWidth;
        ctx.stroke();
      }
    }
    ctx.beginPath();
    ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = hitVisuals?.fillColor ?? n.color;
    ctx.fill();
    if (hitVisuals?.hasCurrentHit) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, radius + 1.2, 0, Math.PI * 2);
      ctx.strokeStyle = hitVisuals.level === "strong" ? "#f8fafc" : rgba(n.color, 0.9);
      ctx.lineWidth = hitVisuals.ringWidth;
      ctx.stroke();
    }
    if (n.type === "book") {
      ctx.fillStyle = textColor;
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(n.chapterCount ?? 0), n.x, n.y);
    }
  });
  if (hoveredNode?.x != null && hoveredNode.y != null) {
    ctx.beginPath();
    ctx.arc(
      hoveredNode.x,
      hoveredNode.y,
      getNodeRadius(hoveredNode) + 4,
      0,
      Math.PI * 2
    );
    ctx.strokeStyle = textColor;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  ctx.restore();
}
export {
  buildView,
  draw,
  findNodeAtPosition,
  rebuildGraph
};
