"""Static graph viewer generation."""

from __future__ import annotations

import json
from pathlib import Path


_VIEWER_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>prompt-lib OKF graph</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f7f5ef;
      --ink: #1c2327;
      --muted: #617078;
      --line: #d2d7d3;
      --panel: #ffffff;
      --skill: #2878a8;
      --agent: #2f8f64;
      --hook: #a65f2b;
      --rule: #b1425a;
      --tool: #7557a8;
      --spec: #7b6d2d;
      --codex: #4f7771;
      --template: #8a6848;
      --output: #57617d;
      --edge: #44515a;
      --selected: #d9480f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 25rem;
      grid-template-rows: auto minmax(0, 1fr);
      min-height: 100vh;
    }
    header {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 1rem;
      align-items: end;
      padding: 1.1rem 1.3rem .8rem;
      border-bottom: 1px solid var(--line);
      background: #fffdf8;
    }
    h1 {
      margin: 0;
      font-size: 1.45rem;
      letter-spacing: 0;
    }
    .subtitle {
      margin: .2rem 0 0;
      color: var(--muted);
      font-size: .92rem;
    }
    .stats {
      display: flex;
      gap: .5rem;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .stat, .chip {
      border: 1px solid var(--line);
      border-radius: .4rem;
      background: var(--panel);
      padding: .35rem .55rem;
      font-size: .82rem;
      white-space: nowrap;
    }
    main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      border-right: 1px solid var(--line);
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(12rem, 1fr) auto auto auto;
      gap: .65rem;
      align-items: center;
      padding: .8rem 1rem;
      border-bottom: 1px solid var(--line);
      background: #fbfaf6;
    }
    input, select, button {
      font: inherit;
      color: var(--ink);
    }
    input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: .4rem;
      background: var(--panel);
      padding: .48rem .6rem;
    }
    button {
      border: 1px solid #aeb8b3;
      border-radius: .4rem;
      background: var(--panel);
      padding: .48rem .65rem;
      cursor: pointer;
    }
    button.active {
      border-color: var(--selected);
      color: var(--selected);
      font-weight: 700;
    }
    .graph-frame {
      min-height: 0;
      overflow: auto;
      background:
        linear-gradient(#ece9df 1px, transparent 1px),
        linear-gradient(90deg, #ece9df 1px, transparent 1px);
      background-size: 28px 28px;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
      max-height: calc(100vh - 7rem);
      cursor: grab;
      touch-action: none;
    }
    svg.panning { cursor: grabbing; }
    .edge {
      fill: none;
      stroke: var(--edge);
      stroke-width: 1.5;
      opacity: .45;
      cursor: pointer;
    }
    .edge.structured { stroke-dasharray: 6 4; }
    .edge:hover, .edge.selected {
      stroke: var(--selected);
      opacity: 1;
      stroke-width: 2.8;
    }
    .node {
      cursor: pointer;
    }
    .node circle {
      stroke: #ffffff;
      stroke-width: 2;
      filter: drop-shadow(0 1px 1px rgba(27, 35, 39, .18));
    }
    .node text {
      font-size: 13px;
      paint-order: stroke;
      stroke: #fffdf8;
      stroke-width: 4px;
      stroke-linejoin: round;
      fill: var(--ink);
      pointer-events: none;
    }
    .node .sub {
      font-size: 10px;
      fill: var(--muted);
    }
    .node.selected circle {
      stroke: var(--selected);
      stroke-width: 4;
    }
    .dim {
      opacity: .16;
    }
    .legend {
      display: flex;
      gap: .45rem;
      flex-wrap: wrap;
      padding: .65rem 1rem;
      border-top: 1px solid var(--line);
      background: #fffdf8;
    }
    .legend .chip {
      display: inline-flex;
      align-items: center;
      gap: .35rem;
    }
    .dot {
      width: .7rem;
      height: .7rem;
      border-radius: 50%;
      display: inline-block;
    }
    aside {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      background: #fffdf8;
    }
    .panel-head {
      padding: 1rem;
      border-bottom: 1px solid var(--line);
    }
    .panel-head h2 {
      margin: 0;
      font-size: 1rem;
    }
    #inspector {
      overflow: auto;
      padding: 1rem;
    }
    .section {
      margin-bottom: 1rem;
    }
    .section h3 {
      margin: 0 0 .45rem;
      font-size: .82rem;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: .05em;
    }
    .route {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: .45rem;
      padding: .55rem;
      margin-bottom: .5rem;
      cursor: pointer;
    }
    .route:hover {
      border-color: var(--selected);
    }
    code {
      overflow-wrap: anywhere;
      color: #205c45;
    }
    .mono {
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: .83rem;
    }
    .small {
      color: var(--muted);
      font-size: .84rem;
      line-height: 1.4;
    }
    .footer-note {
      padding: .75rem 1rem;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: .82rem;
    }
    @media (max-width: 960px) {
      .shell {
        grid-template-columns: 1fr;
      }
      aside {
        min-height: 34rem;
      }
      .toolbar {
        grid-template-columns: 1fr 1fr;
      }
      header {
        grid-template-columns: 1fr;
      }
      .stats {
        justify-content: flex-start;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>prompt-lib OKF knowledge map</h1>
        <p class="subtitle">Skill-agent routes, source concepts, and graph evidence generated from OKF metadata.</p>
      </div>
      <div class="stats">
        <span class="stat"><strong>__NODE_COUNT__</strong> nodes</span>
        <span class="stat"><strong>__EDGE_COUNT__</strong> routes</span>
        <span class="stat"><strong>0</strong> external calls</span>
      </div>
    </header>
    <main>
      <div class="toolbar">
        <input id="search" type="search" placeholder="Search agents, skills, resources, evidence">
        <select id="type-filter" aria-label="Node type filter"></select>
        <select id="edge-filter" aria-label="Edge kind filter"></select>
        <div>
          <button id="mode-routes" class="active" type="button">Route map</button>
          <button id="mode-all" type="button">All concepts</button>
          <button id="reset" type="button">Reset</button>
        </div>
      </div>
      <div class="graph-frame">
        <svg id="node-link-map" role="img" aria-label="OKF node link graph"></svg>
      </div>
      <div id="legend" class="legend"></div>
    </main>
    <aside>
      <div class="panel-head">
        <h2>Inspector</h2>
        <p class="subtitle">Click a node, edge, or route to see why it exists.</p>
      </div>
      <div id="inspector"></div>
      <div class="footer-note">Default view shows connected skill-agent routes. Switch to all concepts to audit coverage.</div>
    </aside>
  </div>
  <script type="application/json" id="graph-data">__GRAPH_JSON__</script>
  <script>
    const graph = JSON.parse(document.getElementById("graph-data").textContent);
    const nodeById = new Map(graph.nodes.map(node => [node.id, node]));
    const svg = document.getElementById("node-link-map");
    const inspector = document.getElementById("inspector");
    const searchInput = document.getElementById("search");
    const typeFilter = document.getElementById("type-filter");
    const edgeFilter = document.getElementById("edge-filter");
    const modeRoutes = document.getElementById("mode-routes");
    const modeAll = document.getElementById("mode-all");
    const resetButton = document.getElementById("reset");
    const legend = document.getElementById("legend");
    const palette = {
      agent: "#2f8f64",
      skill: "#2878a8",
      hook: "#a65f2b",
      rule: "#b1425a",
      tool: "#7557a8",
      spec: "#7b6d2d",
      codex: "#4f7771",
      template: "#8a6848",
      output_style: "#57617d"
    };
    const labels = {
      output_style: "output style"
    };
    const typeOrder = ["skill", "agent", "hook", "rule", "tool", "template", "codex", "spec", "output_style"];
    const state = {
      mode: "routes",
      search: "",
      type: "all",
      edge: "all",
      selected: null
    };

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[ch]));
    }

    function textForNode(node) {
      return [node.id, node.label, node.type, node.resource, ...(node.tags || [])].join(" ").toLowerCase();
    }

    function textForEdge(edge) {
      const evidence = (edge.evidence || []).map(item => `${item.resource} ${item.text}`).join(" ");
      return [edge.id, edge.source, edge.target, edge.target_ref, edge.kind, edge.reason, evidence].join(" ").toLowerCase();
    }

    function matchesSearchNode(node) {
      return !state.search || textForNode(node).includes(state.search);
    }

    function matchesSearchEdge(edge) {
      return !state.search || textForEdge(edge).includes(state.search);
    }

    function filteredGraph() {
      const edgeCandidates = graph.edges.filter(edge => {
        if (state.edge !== "all" && edge.kind !== state.edge) return false;
        if (!matchesSearchEdge(edge)) {
          const source = nodeById.get(edge.source);
          const target = nodeById.get(edge.target);
          if (!source && !target) return false;
          if (source && matchesSearchNode(source)) return true;
          if (target && matchesSearchNode(target)) return true;
          return false;
        }
        return true;
      });
      const connected = new Set();
      for (const edge of edgeCandidates) {
        connected.add(edge.source);
        if (edge.target) connected.add(edge.target);
      }
      let nodes = graph.nodes.filter(node => {
        if (state.mode === "routes" && !connected.has(node.id)) return false;
        if (state.type !== "all" && node.type !== state.type) return false;
        return matchesSearchNode(node) || connected.has(node.id);
      });
      const visible = new Set(nodes.map(node => node.id));
      const edges = edgeCandidates.filter(edge => visible.has(edge.source) && (!edge.target || visible.has(edge.target)));
      if (state.mode === "routes") {
        const routeVisible = new Set();
        for (const edge of edges) {
          routeVisible.add(edge.source);
          if (edge.target) routeVisible.add(edge.target);
        }
        nodes = nodes.filter(node => routeVisible.has(node.id));
      }
      return { nodes, edges };
    }

    function populateControls() {
      const types = ["all", ...typeOrder.filter(type => graph.nodes.some(node => node.type === type))];
      typeFilter.innerHTML = types.map(type => `<option value="${esc(type)}">${esc(labels[type] || type)}</option>`).join("");
      const edgeKinds = ["all", ...Array.from(new Set(graph.edges.map(edge => edge.kind))).sort()];
      edgeFilter.innerHTML = edgeKinds.map(kind => `<option value="${esc(kind)}">${esc(kind)}</option>`).join("");
      legend.innerHTML = typeOrder
        .filter(type => graph.nodes.some(node => node.type === type))
        .map(type => `<span class="chip"><span class="dot" style="background:${palette[type]}"></span>${esc(labels[type] || type)}</span>`)
        .join("");
    }

    function layout(nodes) {
      const grouped = new Map();
      for (const node of nodes) {
        const key = state.mode === "routes" && !["skill", "agent"].includes(node.type) ? "other" : node.type;
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(node);
      }
      const keys = state.mode === "routes"
        ? ["skill", "agent", "other"].filter(key => grouped.has(key))
        : typeOrder.filter(key => grouped.has(key));
      const width = Math.max(760, keys.length * 200 + 120);
      const maxRows = Math.max(1, ...keys.map(key => grouped.get(key).length));
      const height = Math.max(360, maxRows * 34 + 120);
      const positions = new Map();
      keys.forEach((key, column) => {
        const list = grouped.get(key).sort((a, b) => a.label.localeCompare(b.label));
        const x = keys.length === 1 ? width / 2 : 90 + column * ((width - 180) / Math.max(1, keys.length - 1));
        list.forEach((node, row) => {
          const y = 64 + row * 34;
          positions.set(node.id, { x, y });
        });
      });
      return { width, height, positions };
    }

    function nodeDegree(edges) {
      const counts = new Map();
      for (const edge of edges) {
        counts.set(edge.source, (counts.get(edge.source) || 0) + 1);
        if (edge.target) counts.set(edge.target, (counts.get(edge.target) || 0) + 1);
      }
      return counts;
    }

    function edgePath(start, end) {
      if (!start || !end) return "";
      const dx = Math.max(70, Math.abs(end.x - start.x) * .48);
      return `M ${start.x} ${start.y} C ${start.x + dx} ${start.y}, ${end.x - dx} ${end.y}, ${end.x} ${end.y}`;
    }

    function setSelection(id) {
      state.selected = id;
      render();
    }

    function render() {
      const { nodes, edges } = filteredGraph();
      const { width, height, positions } = layout(nodes);
      const degree = nodeDegree(edges);
      fitView(width, height);
      svg.innerHTML = `
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#44515a"></path>
          </marker>
        </defs>
      `;
      const selectedEdge = graph.edges.find(edge => edge.id === state.selected);
      const selectedNode = nodeById.get(state.selected);
      const neighbors = new Set();
      if (selectedNode) {
        for (const edge of graph.edges) {
          if (edge.source === selectedNode.id) {
            neighbors.add(edge.target);
          }
          if (edge.target === selectedNode.id) {
            neighbors.add(edge.source);
          }
        }
      }
      const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
      for (const edge of edges) {
        const start = positions.get(edge.source);
        const end = edge.target ? positions.get(edge.target) : null;
        if (!start || !end) continue;
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", edgePath(start, end));
        path.setAttribute("marker-end", "url(#arrow)");
        path.dataset.id = edge.id;
        path.classList.add("edge", edge.confidence || "explicit");
        if (state.selected === edge.id) path.classList.add("selected");
        if (selectedNode && edge.source !== selectedNode.id && edge.target !== selectedNode.id) path.classList.add("dim");
        path.addEventListener("click", () => setSelection(edge.id));
        edgeLayer.appendChild(path);
      }
      for (const node of nodes) {
        const pos = positions.get(node.id);
        if (!pos) continue;
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
        g.dataset.id = node.id;
        g.classList.add("node");
        if (state.selected === node.id) g.classList.add("selected");
        if (selectedEdge && node.id !== selectedEdge.source && node.id !== selectedEdge.target) g.classList.add("dim");
        if (selectedNode && node.id !== selectedNode.id && !neighbors.has(node.id)) g.classList.add("dim");
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("r", String(Math.min(18, 8 + (degree.get(node.id) || 0) * 2)));
        circle.setAttribute("fill", palette[node.type] || "#68737a");
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", "24");
        label.setAttribute("y", "4");
        label.textContent = node.label.length > 30 ? `${node.label.slice(0, 28)}...` : node.label;
        const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
        sub.setAttribute("class", "sub");
        sub.setAttribute("x", "24");
        sub.setAttribute("y", "19");
        sub.textContent = labels[node.type] || node.type;
        g.append(circle, label, sub);
        g.addEventListener("click", () => setSelection(node.id));
        nodeLayer.appendChild(g);
      }
      svg.append(edgeLayer, nodeLayer);
      renderInspector(nodes, edges);
    }

    function routeCards(edges, limit = 8) {
      return edges.slice(0, limit).map(edge => {
        const target = nodeById.get(edge.target);
        return `<div class="route" data-edge="${esc(edge.id)}">
          <div><strong>${esc(nodeById.get(edge.source)?.label || edge.source)}</strong> to <strong>${esc(target?.label || edge.target_ref)}</strong></div>
          <div class="small">${esc(edge.reason || edge.kind)}</div>
        </div>`;
      }).join("");
    }

    function renderInspector(visibleNodes, visibleEdges) {
      const selectedEdge = graph.edges.find(edge => edge.id === state.selected);
      const selectedNode = nodeById.get(state.selected);
      if (selectedEdge) {
        const evidence = (selectedEdge.evidence || []).map(item => (
          `<div class="route"><div class="mono">${esc(item.resource)}${item.line ? `:${item.line}` : ""}</div><div>${esc(item.text)}</div></div>`
        )).join("");
        inspector.innerHTML = `
          <div class="section"><h3>Route</h3><p><code>${esc(selectedEdge.source)}</code><br>to<br><code>${esc(selectedEdge.target || selectedEdge.target_ref)}</code></p></div>
          <div class="section"><h3>Why</h3><p>${esc(selectedEdge.reason)}</p><p class="small">Confidence: ${esc(selectedEdge.confidence)}</p></div>
          <div class="section"><h3>Evidence</h3>${evidence || "<p class='small'>No evidence recorded.</p>"}</div>
        `;
        return;
      }
      if (selectedNode) {
        const related = graph.edges.filter(edge => edge.source === selectedNode.id || edge.target === selectedNode.id);
        inspector.innerHTML = `
          <div class="section"><h3>Concept</h3><h2>${esc(selectedNode.label)}</h2><p><code>${esc(selectedNode.id)}</code></p><p class="small">${esc(labels[selectedNode.type] || selectedNode.type)} from ${esc(selectedNode.resource)}</p></div>
          <div class="section"><h3>Connections</h3>${routeCards(related, 12) || "<p class='small'>No visible routes.</p>"}</div>
        `;
      } else {
        const topAgents = Array.from(new Map());
        for (const edge of graph.edges) {
          if (!edge.target) continue;
          const target = nodeById.get(edge.target);
          if (!target || target.type !== "agent") continue;
          const item = topAgents.get(edge.target) || { node: target, count: 0 };
          item.count += 1;
          topAgents.set(edge.target, item);
        }
        const top = Array.from(topAgents.values()).sort((a, b) => b.count - a.count).slice(0, 6);
        inspector.innerHTML = `
          <div class="section"><h3>Visible graph</h3><p><strong>${visibleNodes.length}</strong> concepts and <strong>${visibleEdges.length}</strong> routes match the current filters.</p></div>
          <div class="section"><h3>Top routed agents</h3>${top.map(item => `<div class="route" data-node="${esc(item.node.id)}"><strong>${esc(item.node.label)}</strong><div class="small">${item.count} incoming route${item.count === 1 ? "" : "s"}</div></div>`).join("")}</div>
          <div class="section"><h3>Sample routes</h3>${routeCards(visibleEdges, 6)}</div>
        `;
      }
      inspector.querySelectorAll("[data-edge]").forEach(item => item.addEventListener("click", () => setSelection(item.dataset.edge)));
      inspector.querySelectorAll("[data-node]").forEach(item => item.addEventListener("click", () => setSelection(item.dataset.node)));
    }

    searchInput.addEventListener("input", event => {
      state.search = event.target.value.trim().toLowerCase();
      state.selected = null;
      render();
    });
    typeFilter.addEventListener("change", event => {
      state.type = event.target.value;
      state.selected = null;
      render();
    });
    edgeFilter.addEventListener("change", event => {
      state.edge = event.target.value;
      state.selected = null;
      render();
    });
    modeRoutes.addEventListener("click", () => {
      state.mode = "routes";
      modeRoutes.classList.add("active");
      modeAll.classList.remove("active");
      state.selected = null;
      render();
    });
    modeAll.addEventListener("click", () => {
      state.mode = "all";
      modeAll.classList.add("active");
      modeRoutes.classList.remove("active");
      state.selected = null;
      render();
    });
    resetButton.addEventListener("click", () => {
      state.mode = "routes";
      state.search = "";
      state.type = "all";
      state.edge = "all";
      state.selected = null;
      searchInput.value = "";
      typeFilter.value = "all";
      edgeFilter.value = "all";
      modeRoutes.classList.add("active");
      modeAll.classList.remove("active");
      render();
    });

    // --- pan + zoom via viewBox; render() calls fitView() to refit on every redraw ---
    let viewBox = { x: 0, y: 0, w: 0, h: 0 };
    function applyView() {
      svg.setAttribute("viewBox", `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`);
    }
    function fitView(w, h) {
      svg.dataset.baseW = w;
      viewBox = { x: 0, y: 0, w: w, h: h };
      applyView();
    }
    svg.addEventListener("wheel", event => {
      event.preventDefault();
      if (!viewBox.w) return;
      const rect = svg.getBoundingClientRect();
      const px = viewBox.x + (event.clientX - rect.left) / rect.width * viewBox.w;
      const py = viewBox.y + (event.clientY - rect.top) / rect.height * viewBox.h;
      const baseW = Number(svg.dataset.baseW) || viewBox.w;
      let nw = viewBox.w * (event.deltaY < 0 ? 0.85 : 1.18);
      nw = Math.min(Math.max(nw, baseW * 0.2), baseW * 3);
      const ratio = nw / viewBox.w;
      viewBox = { x: px - (px - viewBox.x) * ratio, y: py - (py - viewBox.y) * ratio, w: nw, h: viewBox.h * ratio };
      applyView();
    }, { passive: false });
    let drag = null;
    svg.addEventListener("pointerdown", event => {
      drag = { x: event.clientX, y: event.clientY };
      svg.classList.add("panning");
      svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener("pointermove", event => {
      if (!drag || !viewBox.w) return;
      const rect = svg.getBoundingClientRect();
      viewBox.x -= (event.clientX - drag.x) / rect.width * viewBox.w;
      viewBox.y -= (event.clientY - drag.y) / rect.height * viewBox.h;
      drag = { x: event.clientX, y: event.clientY };
      applyView();
    });
    function endDrag() { drag = null; svg.classList.remove("panning"); }
    svg.addEventListener("pointerup", endDrag);
    svg.addEventListener("pointercancel", endDrag);

    populateControls();
    render();
  </script>
</body>
</html>
"""


def generate_viewer(graph_path: Path, out_path: Path | None = None) -> Path:
    graph_path = Path(graph_path)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    out_path = Path(out_path or graph_path.with_name("graph.html"))
    graph_json = json.dumps(graph, indent=2, sort_keys=True)
    script_json = graph_json.replace("<", "\\u003c").replace(
        "</script", "\\u003c/script"
    )
    html_text = (
        _VIEWER_TEMPLATE.replace("__GRAPH_JSON__", script_json)
        .replace("__NODE_COUNT__", str(len(graph.get("nodes", []))))
        .replace("__EDGE_COUNT__", str(len(graph.get("edges", []))))
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
    manifest_path = out_path.parent / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rel = str(out_path.relative_to(out_path.parent)).replace("\\", "/")
        generated = set(manifest.get("generated_files", []))
        generated.add(rel)
        manifest["generated_files"] = sorted(generated)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return out_path
