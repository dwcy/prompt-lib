// Curated-profile edit state: baseline/draft tracking, dirty detection, the ON-toggle's
// clear/restore behavior, and the native folder-browse flow — kept out of the component tree.
import { useEffect, useMemo, useRef, useState } from "react";
import type { EnvEntry, EnvScope } from "@/api/securityEnvironment";

export interface UseEnvironmentProfileResult {
  baseline: Record<string, string>;
  draft: Record<string, string>;
  dirtyValues: Record<string, string>;
  dirtyCount: number;
  browseError: string | null;
  setValue: (name: string, value: string) => void;
  revertOne: (name: string) => void;
  revertAll: () => void;
  toggleEntry: (entry: EnvEntry) => void;
  browseFor: (entry: EnvEntry) => Promise<void>;
}

export function useEnvironmentProfile(
  scope: EnvScope,
  entries: EnvEntry[] | undefined,
): UseEnvironmentProfileResult {
  const [baseline, setBaseline] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [browseError, setBrowseError] = useState<string | null>(null);
  const lastNonEmpty = useRef<Record<string, string>>({});

  useEffect(() => {
    if (entries === undefined || scope !== "curated") return;
    const next = Object.fromEntries(
      entries.map((entry) => [entry.name, entry.value_redacted || entry.default]),
    );
    setBaseline(next);
    setDraft(next);
  }, [entries, scope]);

  const dirtyValues = useMemo(() => {
    if (entries === undefined || scope !== "curated") return {};
    return Object.fromEntries(
      entries
        .filter((entry) => entry.editable && (draft[entry.name] ?? "") !== baseline[entry.name])
        .map((entry) => [entry.name, draft[entry.name] ?? ""]),
    );
  }, [baseline, draft, entries, scope]);

  function setValue(name: string, value: string): void {
    setDraft((state) => ({ ...state, [name]: value }));
  }

  function revertOne(name: string): void {
    setDraft((state) => ({ ...state, [name]: baseline[name] ?? "" }));
  }

  function revertAll(): void {
    setDraft(baseline);
  }

  function toggleEntry(entry: EnvEntry): void {
    const current = draft[entry.name] ?? "";
    if (current.trim() !== "") {
      lastNonEmpty.current[entry.name] = current;
      setValue(entry.name, "");
      return;
    }
    const restored = lastNonEmpty.current[entry.name] ?? baseline[entry.name] ?? entry.default;
    setValue(entry.name, restored);
  }

  async function browseFor(entry: EnvEntry): Promise<void> {
    setBrowseError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") setValue(entry.name, selected);
    } catch {
      setBrowseError("Native folder picker failed; type the path manually.");
    }
  }

  return {
    baseline,
    draft,
    dirtyValues,
    dirtyCount: Object.keys(dirtyValues).length,
    browseError,
    setValue,
    revertOne,
    revertAll,
    toggleEntry,
    browseFor,
  };
}
