// Maps OKF concept node types to the design-token colors shared by GraphCanvas node dots and
// the graph legend overlay, so both stay in sync without hardcoding hex values in either place.
export interface NodeTypeStyle {
  label: string;
  colorVar: string;
}

const KNOWN_NODE_TYPES: Record<string, NodeTypeStyle> = {
  agent: { label: "agent", colorVar: "--accent" },
  skill: { label: "skill", colorVar: "--group-repo" },
  hook: { label: "hook", colorVar: "--group-infrastructure" },
  rule: { label: "rule", colorVar: "--group-reference" },
  tool: { label: "tool", colorVar: "--group-agents" },
  spec: { label: "spec", colorVar: "--status-danger" },
  codex: { label: "codex", colorVar: "--muted-2" },
  template: { label: "template", colorVar: "--muted-3" },
  output_style: { label: "output style", colorVar: "--muted" },
};

const FALLBACK_STYLE: NodeTypeStyle = { label: "other", colorVar: "--muted" };

export function nodeTypeStyle(type: string): NodeTypeStyle {
  const known = KNOWN_NODE_TYPES[type];
  if (known !== undefined) return known;
  return { label: type.replace(/_/g, " "), colorVar: FALLBACK_STYLE.colorVar };
}

export function nodeTypeClass(type: string): string {
  return type.replace(/[^a-z0-9_-]/gi, "-").toLowerCase();
}

export function orderedPresentTypes(types: Iterable<string>): string[] {
  const known = Object.keys(KNOWN_NODE_TYPES);
  const present = new Set(types);
  const ordered = known.filter((type) => present.has(type));
  const extra = [...present].filter((type) => !known.includes(type)).sort();
  return [...ordered, ...extra];
}
