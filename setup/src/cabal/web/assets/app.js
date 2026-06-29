(() => {
  "use strict";

  const SCHEMA_VERSION = "cabal-web.v1";
  const endpoints = {
    health: "/api/health",
    overview: "/api/overview",
    tools: "/api/tools",
    knowledge: "/api/knowledge",
    project: "/api/project-health",
    diagnostics: "/api/diagnostics"
  };
  const state = {
    view: "overview",
    health: null,
    overview: null,
    tools: null,
    knowledge: null,
    project: null,
    diagnostics: null,
    selectedTool: null,
    selectedKnowledge: null,
    filters: {
      toolSearch: "",
      toolCategory: "all",
      toolStatus: "all",
      toolChannel: "all",
      knowledgeSearch: "",
      knowledgeType: "all",
      knowledgeRelation: "all"
    }
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
  }

  function redact(value) {
    return String(value ?? "")
      .replace(/\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+/gi, "[redacted]")
      .replace(/\b(?:Bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}\b/gi, "[redacted]")
      .replace(/\bghp_[A-Za-z0-9_]{20,}\b/g, "[redacted]")
      .replace(/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, "[redacted]")
      .replace(/\b(?:sk|sk-ant|sk-proj)-[A-Za-z0-9_-]{20,}\b/g, "[redacted]");
  }

  function safeText(value) {
    return escapeHtml(redact(value));
  }

  async function fetchEnvelope(key) {
    setStatus(key, "loading", `Loading ${labelFor(key)}...`);
    try {
      const response = await fetch(endpoints[key], { cache: "no-store" });
      const envelope = await response.json();
      if (envelope.schema_version !== SCHEMA_VERSION) {
        throw new Error(`Schema mismatch: ${envelope.schema_version || "missing"}`);
      }
      state[key] = envelope;
      $("#schema-badge").textContent = envelope.schema_version;
      if (!response.ok || envelope.status === "error") {
        const message = envelope.error?.message || `${labelFor(key)} failed`;
        setStatus(key, "error", message);
      } else {
        setStatus(key, envelope.status, `${labelFor(key)} loaded ${formatTime(envelope.captured_at)}`);
      }
      render();
    } catch (error) {
      state[key] = { status: "error", error: { message: error.message }, data: null };
      setStatus(key, "error", `${labelFor(key)} failed: ${error.message}`);
      render();
    }
  }

  function labelFor(key) {
    return {
      health: "Health",
      overview: "Overview",
      tools: "Tools",
      knowledge: "Knowledge",
      project: "Project health",
      infrastructure: "Infrastructure overview",
      github: "GitHub",
      agent: "Agent setup",
      diagnostics: "Diagnostics"
    }[key] || key;
  }

  function formatTime(value) {
    if (!value) return "";
    try {
      return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function setStatus(key, status, message) {
    const el = $(`#${key === "project" ? "project" : key}-status`);
    if (!el) return;
    el.dataset.state = status;
    el.textContent = redact(message);
  }

  function render() {
    renderOverview();
    renderAgentSetup();
    renderTools();
    renderKnowledge();
    renderProject();
    renderInfrastructure();
    renderGithub();
    renderDiagnostics();
  }

  function renderOverview() {
    const data = state.overview?.data;
    if (!data) return;
    $("#overview-metrics").innerHTML = [
      metric("Tools", data.tool_count, "catalog entries"),
      metric("Knowledge", data.knowledge_available ? "Ready" : "Missing", `${data.knowledge_counts?.nodes || 0} nodes`),
      metric("Project", Object.entries(data.project_health_counts || {}).map(([k, v]) => `${k}: ${v}`).join(" / ") || "No data", "section states"),
      metric("Diagnostics", data.diagnostic_count, "events")
    ].join("");
    $("#overview-terminal").innerHTML = (data.terminal_sections || data.setup_groups || [])
      .map((group) => setupGroupCard(group))
      .join("");
    $("#overview-sections").innerHTML = (data.sections || []).map((section) => `
      <article class="section-card" data-state="${safeText(section.state)}">
        <strong>${safeText(section.section.replace("_", " "))}</strong>
        <span>${safeText(section.message || section.state)}</span>
      </article>
    `).join("");
  }

  function metric(label, value, hint) {
    return `
      <article class="metric-card">
        <span>${safeText(label)}</span>
        <strong>${safeText(value)}</strong>
        <small>${safeText(hint)}</small>
      </article>
    `;
  }

  function renderAgentSetup() {
    const group = (state.overview?.data?.setup_groups || []).find((item) => item.id === "agent_setup");
    if (!group) return;
    const status = $("#agent-status");
    status.dataset.state = "ok";
    status.textContent = `${group.title} loaded from overview`;
    $("#agent-summary").innerHTML = setupGroupCard(group, true);
  }

  function setupGroupCard(group, expanded = false) {
    return `
      <article class="setup-card" data-group="${safeText(group.id)}">
        <div class="setup-card-head">
          <span>${safeText(group.title)}</span>
          <strong>${safeText(group.summary)}</strong>
        </div>
        <div class="setup-items ${expanded ? "is-expanded" : ""}">
          ${(group.items || []).map((item) => `
            <div class="setup-item" data-state="${safeText(item.state)}">
              <span>${safeText(item.label)}</span>
              <strong>${safeText(item.value)}</strong>
              <small>${safeText(item.hint)}</small>
            </div>
          `).join("")}
        </div>
      </article>
    `;
  }

  function renderTools() {
    const data = state.tools?.data;
    if (!data) return;
    populateSelect("#tool-category", ["all", ...(data.categories || []).map((c) => c.name)], state.filters.toolCategory);
    populateSelect("#tool-status", ["all", ...Object.keys(data.status_counts || {})], state.filters.toolStatus);
    populateSelect("#tool-channel", ["all", ...Object.keys(data.install_channel_counts || {})], state.filters.toolChannel);
    const items = filteredTools(data.items || []);
    $("#tool-categories").innerHTML = (data.categories || []).map((category) => `
      <button type="button" class="rail-item ${state.filters.toolCategory === category.name ? "is-active" : ""}" data-tool-category="${safeText(category.name)}">
        <span>${safeText(category.name)}</span><b>${category.count}</b>
      </button>
    `).join("");
    $("#tool-results").innerHTML = items.map((item) => `
      <button type="button" class="tool-row" role="listitem" data-tool-key="${safeText(item.key)}">
        <span class="status-dot" data-state="${safeText(item.status)}"></span>
        <span><strong>${safeText(item.label)}</strong><small>${safeText(item.category)}</small></span>
        <em>${safeText(item.install_channel)}</em>
      </button>
    `).join("") || emptyState("No tools match the current filters.");
    const selected = items.find((item) => item.key === state.selectedTool) || items[0];
    state.selectedTool = selected?.key || null;
    renderToolDetail(selected);
  }

  function filteredTools(items) {
    const needle = state.filters.toolSearch.toLowerCase();
    return items.filter((item) => {
      const hay = [item.label, item.category, item.description, item.install_channel, ...(item.badges || [])].join(" ").toLowerCase();
      if (needle && !hay.includes(needle)) return false;
      if (state.filters.toolCategory !== "all" && item.category !== state.filters.toolCategory) return false;
      if (state.filters.toolStatus !== "all" && item.status !== state.filters.toolStatus) return false;
      if (state.filters.toolChannel !== "all" && item.install_channel !== state.filters.toolChannel) return false;
      return true;
    });
  }

  function renderToolDetail(item) {
    const el = $("#tool-detail");
    if (!item) {
      el.innerHTML = emptyState("Select a tool to inspect.");
      return;
    }
    el.innerHTML = `
      <h3>${safeText(item.label)}</h3>
      <p>${safeText(item.description)}</p>
      <dl>
        ${detail("Status", item.status)}
        ${detail("Category", item.category)}
        ${detail("Install channel", item.install_channel)}
        ${detail("Source", item.source_status)}
        ${detail("Platforms", (item.platforms || []).join(", "))}
        ${detail("Version metadata", item.version_provider || "unavailable")}
        ${detail("Backup policy", item.backup_policy || "none")}
      </dl>
      ${item.source_url ? `<a class="safe-link" href="${safeText(item.source_url)}" target="_blank" rel="noreferrer">${safeText(item.source_label || "Read more")}</a>` : ""}
      ${(item.safety_notes || []).map((note) => `<p class="note">${safeText(note)}</p>`).join("")}
    `;
  }

  function renderKnowledge() {
    const data = state.knowledge?.data;
    if (!data) return;
    populateSelect("#knowledge-type", ["all", ...Object.keys(data.counts?.by_type || {})], state.filters.knowledgeType);
    populateSelect("#knowledge-relation", ["all", ...Object.keys(data.counts?.by_relation || {})], state.filters.knowledgeRelation);
    if (!data.available) {
      $("#knowledge-routes").innerHTML = emptyState("No graph bundle exists. Export OKF to populate this view.");
      $("#knowledge-detail").innerHTML = emptyState("No concept selected.");
      return;
    }
    const nodesById = new Map((data.nodes || []).map((node) => [node.id, node]));
    const edges = filteredEdges(data.edges || [], nodesById);
    $("#knowledge-routes").innerHTML = edges.map((edge) => `
      <button type="button" class="route-row" data-edge-id="${safeText(edge.id)}">
        <strong>${safeText(nodesById.get(edge.source)?.label || edge.source)}</strong>
        <span>${safeText(edge.kind)}</span>
        <strong>${safeText(nodesById.get(edge.target)?.label || edge.target_ref || "unresolved")}</strong>
      </button>
    `).join("") || emptyState("No relationships match the current filters.");
    const selected = edges.find((edge) => edge.id === state.selectedKnowledge) || edges[0];
    state.selectedKnowledge = selected?.id || null;
    renderKnowledgeDetail(selected, nodesById);
  }

  function filteredEdges(edges, nodesById) {
    const needle = state.filters.knowledgeSearch.toLowerCase();
    return edges.filter((edge) => {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      const text = [edge.kind, edge.reason, source?.label, source?.type, target?.label, target?.type, ...(edge.evidence || []).map((ev) => ev.text)].join(" ").toLowerCase();
      if (needle && !text.includes(needle)) return false;
      if (state.filters.knowledgeType !== "all" && source?.type !== state.filters.knowledgeType && target?.type !== state.filters.knowledgeType) return false;
      if (state.filters.knowledgeRelation !== "all" && edge.kind !== state.filters.knowledgeRelation) return false;
      return true;
    });
  }

  function renderKnowledgeDetail(edge, nodesById) {
    const el = $("#knowledge-detail");
    if (!edge) {
      el.innerHTML = emptyState("Select a route to inspect.");
      return;
    }
    el.innerHTML = `
      <h3>${safeText(edge.kind)}</h3>
      <p>${safeText(edge.reason || "No reason recorded.")}</p>
      <dl>
        ${detail("Source", nodesById.get(edge.source)?.label || edge.source)}
        ${detail("Target", nodesById.get(edge.target)?.label || edge.target_ref)}
        ${detail("Confidence", edge.confidence)}
      </dl>
      <h4>Evidence</h4>
      ${(edge.evidence || []).map((item) => `<p class="note"><code>${safeText(item.resource)}${item.line ? `:${item.line}` : ""}</code><br>${safeText(item.text)}</p>`).join("") || "<p class='muted'>No evidence recorded.</p>"}
    `;
  }

  function renderProject() {
    const data = state.project?.data;
    if (!data) return;
    const sections = ["git", "github", "supabase", "vercel"].map((key) => data[key]).filter(Boolean);
    $("#project-sections").innerHTML = sections.map(projectSectionCard).join("");
  }

  function renderInfrastructure() {
    const data = state.project?.data;
    if (!data) return;
    setProjectBackedStatus("infrastructure", "Infrastructure overview", state.project, data);
    const sections = ["git", "github", "supabase", "vercel"].map((key) => data[key]).filter(Boolean);
    $("#infrastructure-sections").innerHTML = sections.map(projectSectionCard).join("");
  }

  function renderGithub() {
    const data = state.project?.data;
    if (!data) return;
    const section = data.github;
    const status = $("#github-status");
    if (status) {
      status.dataset.state = section?.state || state.project?.status || "loading";
      status.textContent = section?.summary || "GitHub data unavailable";
    }
    $("#github-sections").innerHTML = section
      ? projectSectionCard(section)
      : emptyState("No GitHub project data available.");
  }

  function setProjectBackedStatus(key, label, envelope, data) {
    const status = $(`#${key}-status`);
    if (!status) return;
    status.dataset.state = envelope?.status || "ok";
    status.textContent = `${label} loaded ${formatTime(envelope?.captured_at || data?.captured_at)}`;
  }

  function projectSectionCard(section) {
    return `
      <article class="project-card" data-state="${safeText(section.state)}">
        <h3>${safeText(section.title)}</h3>
        <p>${safeText(section.summary)}</p>
        <dl>${(section.facts || []).map((fact) => detail(fact.label, fact.value)).join("")}</dl>
        ${(section.links || []).map((link) => link.url ? `<a class="safe-link" href="${safeText(link.url)}" target="_blank" rel="noreferrer">${safeText(link.label)}</a>` : "").join("")}
        ${section.hint ? `<p class="note">${safeText(section.hint)}</p>` : ""}
      </article>
    `;
  }

  function renderDiagnostics() {
    const data = state.diagnostics?.data;
    if (!data) return;
    $("#diagnostics-list").innerHTML = (data.events || []).map((event) => `
      <article class="diagnostic" data-state="${safeText(event.severity)}">
        <strong>${safeText(event.section)}: ${safeText(event.message)}</strong>
        <span>${safeText(event.timestamp)}</span>
        ${event.details ? `<p>${safeText(event.details)}</p>` : ""}
      </article>
    `).join("") || emptyState("No diagnostics recorded.");
  }

  function detail(label, value) {
    return `<dt>${safeText(label)}</dt><dd>${safeText(value || "none")}</dd>`;
  }

  function populateSelect(selector, values, selected) {
    const el = $(selector);
    if (!el) return;
    const current = Array.from(el.options).map((option) => option.value).join("|");
    const next = values.join("|");
    if (current === next) {
      el.value = values.includes(selected) ? selected : "all";
      return;
    }
    el.innerHTML = values.map((value) => `<option value="${safeText(value)}">${safeText(value)}</option>`).join("");
    el.value = values.includes(selected) ? selected : "all";
  }

  function emptyState(message) {
    return `<div class="empty-state">${safeText(message)}</div>`;
  }

  function bindEvents() {
    $$(".nav-link").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.dataset.viewTarget;
        $$(".nav-link").forEach((item) => item.classList.toggle("is-active", item === button));
        $$(".view").forEach((view) => view.classList.toggle("is-active", view.dataset.view === state.view));
        $("#view-title").textContent = button.dataset.viewTitle || button.textContent;
      });
    });
    $("#refresh-current").addEventListener("click", () => refreshCurrent());
    $$("[data-retry]").forEach((button) => button.addEventListener("click", () => fetchEnvelope(button.dataset.retry)));
    $("#tool-search").addEventListener("input", (event) => { state.filters.toolSearch = event.target.value; renderTools(); });
    $("#tool-category").addEventListener("change", (event) => { state.filters.toolCategory = event.target.value; renderTools(); });
    $("#tool-status").addEventListener("change", (event) => { state.filters.toolStatus = event.target.value; renderTools(); });
    $("#tool-channel").addEventListener("change", (event) => { state.filters.toolChannel = event.target.value; renderTools(); });
    $("#knowledge-search").addEventListener("input", (event) => { state.filters.knowledgeSearch = event.target.value; renderKnowledge(); });
    $("#knowledge-type").addEventListener("change", (event) => { state.filters.knowledgeType = event.target.value; renderKnowledge(); });
    $("#knowledge-relation").addEventListener("change", (event) => { state.filters.knowledgeRelation = event.target.value; renderKnowledge(); });
    document.addEventListener("click", (event) => {
      const category = event.target.closest("[data-tool-category]");
      if (category) {
        state.filters.toolCategory = category.dataset.toolCategory;
        renderTools();
      }
      const tool = event.target.closest("[data-tool-key]");
      if (tool) {
        state.selectedTool = tool.dataset.toolKey;
        renderTools();
      }
      const edge = event.target.closest("[data-edge-id]");
      if (edge) {
        state.selectedKnowledge = edge.dataset.edgeId;
        renderKnowledge();
      }
    });
    document.addEventListener("copy", (event) => {
      const text = document.getSelection()?.toString();
      if (text) {
        event.clipboardData.setData("text/plain", redact(text));
        event.preventDefault();
      }
    });
  }

  function refreshCurrent() {
    const map = { overview: "overview", tools: "tools", knowledge: "knowledge", project: "project", infrastructure: "project", github: "project", agent: "overview", diagnostics: "diagnostics" };
    fetchEnvelope(map[state.view] || "overview");
  }

  function init() {
    $("#backend-url").textContent = window.location.origin || "local backend";
    bindEvents();
    fetchEnvelope("health");
    fetchEnvelope("overview");
    fetchEnvelope("tools");
    fetchEnvelope("knowledge");
    fetchEnvelope("project");
    fetchEnvelope("diagnostics");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
