// Shared shapes + read helpers for the per-section content builders (git.ts/github.ts/
// supabase.ts/vercel.ts/azureDevops.ts) — the dashboard payload (api/schemas.ts's
// dashboardSectionSchema) is a permissive record with no generic facts/links shape, so each
// builder reads its own section's scalar/array fields directly from it.
import type { UnknownSection } from "@/lib/unknownFields";

export interface HealthFactItem {
  label: string;
  meta?: string;
  url?: string;
  /** Indent level for tree-style items (e.g. branch namespace groups). */
  depth?: number;
  /** A non-actionable grouping node (e.g. the "feature" in "feature/x") rather than a leaf. */
  group?: boolean;
  /** Marks the currently checked-out branch. */
  current?: boolean;
  /** The real identifier a row action acts on (full branch name / worktree path) — distinct
   * from `label`, which may be a shortened display form (e.g. a tree leaf's segment name). */
  actionId?: string;
  /** Whether a branch has no upstream ("local") or tracks one ("remote") — rendered as a badge. */
  origin?: "local" | "remote";
}

export interface HealthFact {
  label: string;
  value: string;
  items?: HealthFactItem[];
  nested?: HealthFact[];
  /** Which action buttons (if any) HealthFactRow should render per leaf item. */
  kind?: "branches" | "worktrees";
}

export interface HealthLink {
  label: string;
  url: string;
}

export interface SectionContent {
  summary: string;
  facts: HealthFact[];
  links: HealthLink[];
}

export const NO_SUMMARY = "No summary available";

export function readObjectArray(
  section: UnknownSection,
  key: string,
): Array<Record<string, unknown>> {
  const value = section[key];
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
  );
}

export function pickString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}
