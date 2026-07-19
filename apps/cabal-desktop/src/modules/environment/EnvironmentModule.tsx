import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { queryKeys } from "@/api/queryKeys";
import { type EnvEntry, type EnvScope, useEnvironment } from "@/api/securityEnvironment";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";

type CuratedLane = "all" | "paths" | "runtime";
type SystemEnvFamily = "host" | "filesystem" | "credentials" | "toolchains" | "process";

interface SystemEnvGroup {
  key: SystemEnvFamily;
  label: string;
  description: string;
  entries: EnvEntry[];
}

export function EnvironmentModule() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<EnvScope>("curated");
  const [lane, setLane] = useState<CuratedLane>("all");
  const [queryText, setQueryText] = useState("");
  const [baseline, setBaseline] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [browseError, setBrowseError] = useState<string | null>(null);
  const envQuery = useEnvironment(scope, scope === "system" ? queryText : "");
  const applyAction = useAction("env.apply");

  useEffect(() => {
    if (envQuery.data === undefined || scope !== "curated") return;
    const next = Object.fromEntries(
      envQuery.data.entries.map((entry) => [entry.name, entry.value_redacted || entry.default]),
    );
    setBaseline(next);
    setDraft(next);
  }, [envQuery.data, scope]);

  useEffect(() => {
    if (applyAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("environment") });
  }, [applyAction.phase, queryClient]);

  const dirtyValues = useMemo(() => {
    if (envQuery.data === undefined || scope !== "curated") return {};
    return Object.fromEntries(
      envQuery.data.entries
        .filter((entry) => entry.editable && (draft[entry.name] ?? "") !== baseline[entry.name])
        .map((entry) => [entry.name, draft[entry.name] ?? ""]),
    );
  }, [baseline, draft, envQuery.data, scope]);

  async function browseFor(entry: EnvEntry): Promise<void> {
    setBrowseError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") {
        setDraft((current) => ({ ...current, [entry.name]: selected }));
      }
    } catch {
      setBrowseError("Native folder picker failed; type the path manually.");
    }
  }

  if (envQuery.isPending) return <EmptyState title="Loading environment..." />;
  if (envQuery.isError) {
    return <EmptyState title="Environment unavailable" body={envQuery.error.message} />;
  }

  const normalizedQuery = queryText.trim().toLocaleLowerCase();
  const visibleEntries = envQuery.data.entries.filter((entry) => {
    const matchesQuery =
      normalizedQuery.length === 0 ||
      entry.name.toLocaleLowerCase().includes(normalizedQuery) ||
      entry.description.toLocaleLowerCase().includes(normalizedQuery);
    const matchesLane = lane === "all" || (lane === "paths" ? entry.is_path : !entry.is_path);
    return matchesQuery && (scope === "system" || matchesLane);
  });
  const dirtyCount = Object.keys(dirtyValues).length;
  const stagedEntries = envQuery.data.entries.filter((entry) => entry.name in dirtyValues);
  const stats = environmentStats(envQuery.data.entries);
  const systemGroups = groupSystemEntries(envQuery.data.entries);
  const protectedCount = envQuery.data.entries.filter(isSensitiveEnvironmentEntry).length;

  return (
    <div className="environment-workspace">
      <section className="environment-command-center">
        <div>
          <span className="module-eyebrow select-none">Shell profile</span>
          <h1>{scope === "curated" ? "Environment control" : "System inventory"}</h1>
          <p>{envQuery.data.platform}</p>
        </div>
        <div className="environment-command-center__metrics">
          {scope === "curated" ? (
            <>
              <Metric label="configured" value={stats.configured} tone="ok" />
              <Metric label="fallback" value={stats.defaults} tone="warning" />
              <Metric label="unset" value={stats.unset} tone="neutral" />
              <Metric label="staged" value={dirtyCount} tone="accent" />
            </>
          ) : (
            <>
              <Metric label="namespaces" value={systemGroups.length} tone="accent" />
              <Metric
                label="paths"
                value={envQuery.data.entries.filter((entry) => entry.is_path).length}
                tone="ok"
              />
              <Metric label="protected" value={protectedCount} tone="warning" />
              <Metric label="visible" value={envQuery.data.entries.length} tone="neutral" />
            </>
          )}
        </div>
        <div className="environment-command-center__actions">
          <fieldset className="segmented-control">
            <legend className="visually-hidden">Environment view</legend>
            <button
              type="button"
              className={scope === "curated" ? "is-active" : ""}
              onClick={() => setScope("curated")}
            >
              Profile
            </button>
            <button
              type="button"
              className={scope === "system" ? "is-active" : ""}
              onClick={() => setScope("system")}
            >
              System
            </button>
          </fieldset>
          <input
            type="search"
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
            placeholder="Find a variable"
            aria-label="Find an environment variable"
          />
        </div>
      </section>

      {browseError !== null ? <p className="inline-error">{browseError}</p> : null}

      {scope === "curated" ? (
        <div className="environment-board">
          <aside className="environment-lanes" aria-label="Variable groups">
            <span className="environment-lanes__eyebrow">Profile lanes</span>
            <EnvironmentLane
              label="All variables"
              count={envQuery.data.entries.length}
              active={lane === "all"}
              onSelect={() => setLane("all")}
            />
            <EnvironmentLane
              label="Filesystem"
              count={envQuery.data.entries.filter((entry) => entry.is_path).length}
              active={lane === "paths"}
              onSelect={() => setLane("paths")}
            />
            <EnvironmentLane
              label="Runtime"
              count={envQuery.data.entries.filter((entry) => !entry.is_path).length}
              active={lane === "runtime"}
              onSelect={() => setLane("runtime")}
            />
          </aside>

          <section className="environment-editor">
            <header className="environment-editor__header">
              <div>
                <span className="module-eyebrow">{lane}</span>
                <h2>
                  {lane === "paths"
                    ? "Filesystem map"
                    : lane === "runtime"
                      ? "Runtime values"
                      : "Curated profile"}
                </h2>
              </div>
              <span>{visibleEntries.length} variables</span>
            </header>
            <div className="environment-editor__rows">
              {visibleEntries.length === 0 ? (
                <EmptyState title="No variables matched" />
              ) : (
                visibleEntries.map((entry) => (
                  <CuratedEnvRow
                    key={entry.name}
                    entry={entry}
                    value={draft[entry.name] ?? ""}
                    dirty={entry.name in dirtyValues}
                    onChange={(value) =>
                      setDraft((current) => ({ ...current, [entry.name]: value }))
                    }
                    onBrowse={() => void browseFor(entry)}
                    onRevert={() =>
                      setDraft((current) => ({
                        ...current,
                        [entry.name]: baseline[entry.name] ?? "",
                      }))
                    }
                  />
                ))
              )}
            </div>
          </section>

          <aside className="environment-stage" aria-label="Staged environment changes">
            <header>
              <div>
                <span className="module-eyebrow">Change queue</span>
                <h2>{dirtyCount === 0 ? "Profile unchanged" : `${dirtyCount} staged`}</h2>
              </div>
              <StatePill variant={dirtyCount === 0 ? "ok" : "update"} />
            </header>
            <div className="environment-stage__items">
              {stagedEntries.length === 0 ? (
                <p>Edits appear here before they are written to future shells.</p>
              ) : (
                stagedEntries.map((entry) => (
                  <div key={entry.name}>
                    <strong>{entry.name}</strong>
                    <code>{draft[entry.name]}</code>
                  </div>
                ))
              )}
            </div>
            <div className="environment-stage__actions">
              <button type="button" disabled={dirtyCount === 0} onClick={() => setDraft(baseline)}>
                Revert all
              </button>
              <button
                type="button"
                disabled={dirtyCount === 0 || applyAction.phase === "preparing"}
                onClick={() => applyAction.prepare({ values: dirtyValues })}
              >
                Apply {dirtyCount}
              </button>
            </div>
          </aside>
        </div>
      ) : (
        <SystemEnvironmentInventory entries={visibleEntries} />
      )}

      <ConfirmDialog
        isOpen={applyAction.phase !== "idle" && applyAction.phase !== "succeeded"}
        actionTitle="Apply environment values"
        ticket={applyAction.ticket}
        phase={applyAction.phase}
        reviewNotice={applyAction.reviewNotice}
        error={applyAction.error}
        onConfirm={applyAction.confirm}
        onCancel={applyAction.reset}
      />
    </div>
  );
}

function EnvironmentLane({
  label,
  count,
  active,
  onSelect,
}: {
  label: string;
  count: number;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`environment-lanes__item${active ? " is-active" : ""}`}
      onClick={onSelect}
    >
      <span>{label}</span>
      <strong>{count}</strong>
    </button>
  );
}

function CuratedEnvRow({
  entry,
  value,
  dirty,
  onChange,
  onBrowse,
  onRevert,
}: {
  entry: EnvEntry;
  value: string;
  dirty: boolean;
  onChange: (value: string) => void;
  onBrowse: () => void;
  onRevert: () => void;
}) {
  return (
    <article className={`environment-row${dirty ? " is-dirty" : ""}`}>
      <div className="environment-row__identity">
        <code>{entry.name}</code>
        <small>{entry.description || entry.default || "No description"}</small>
      </div>
      <div className="environment-row__value">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          spellCheck={false}
          aria-label={`${entry.name} value`}
        />
        {entry.is_path ? (
          <button type="button" onClick={onBrowse}>
            Browse
          </button>
        ) : null}
        {dirty ? (
          <button type="button" onClick={onRevert}>
            Revert
          </button>
        ) : null}
      </div>
      <StatePill
        variant={dirty ? "update" : sourceVariant(entry.source)}
        label={dirty ? "staged" : entry.source}
      />
    </article>
  );
}

function SystemEnvironmentInventory({ entries }: { entries: EnvEntry[] }) {
  const groups = groupSystemEntries(entries);
  const maxGroupSize = Math.max(...groups.map((group) => group.entries.length), 1);

  return (
    <section className="system-environment-inventory">
      <header className="system-environment-inventory__header">
        <div>
          <span className="module-eyebrow">Process inheritance map</span>
          <h2>System namespaces</h2>
          <p>Read-only values inherited by Cabal, Claude, and every child process they launch.</p>
        </div>
        <StatePill variant="unavailable" label="read only" />
      </header>

      {groups.length === 0 ? (
        <EmptyState title="No variables matched" />
      ) : (
        <>
          <nav className="system-environment-topology" aria-label="Environment namespaces">
            {groups.map((group, index) => (
              <a key={group.key} href={`#system-env-${group.key}`}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{group.label}</strong>
                <small>{group.entries.length}</small>
                <i aria-hidden="true">
                  <span style={{ width: `${(group.entries.length / maxGroupSize) * 100}%` }} />
                </i>
              </a>
            ))}
          </nav>

          <div className="system-environment-groups">
            {groups.map((group, index) => (
              <section key={group.key} id={`system-env-${group.key}`}>
                <header>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{group.label}</h3>
                    <p>{group.description}</p>
                  </div>
                  <strong>{group.entries.length}</strong>
                </header>
                <div className="system-environment-group__rows">
                  {group.entries.map((entry) => (
                    <div className="system-environment-entry" key={entry.name}>
                      <span className="system-environment-entry__identity">
                        <strong>{entry.name}</strong>
                        <small>{entry.description || environmentEntryRole(entry)}</small>
                      </span>
                      <code>{entry.value_redacted || "not reported"}</code>
                      <StatePill
                        variant={systemEntryVariant(entry)}
                        label={systemEntryLabel(entry)}
                      />
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "warning" | "neutral" | "accent";
}) {
  return (
    <span className={`environment-metric environment-metric--${tone}`}>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function environmentStats(entries: EnvEntry[]) {
  return {
    configured: entries.filter((entry) => entry.source === "system").length,
    defaults: entries.filter((entry) => entry.source === "default").length,
    unset: entries.filter((entry) => entry.source === "unset").length,
  };
}

function sourceVariant(source: string): StatePillVariant {
  switch (source) {
    case "system":
      return "ok";
    case "default":
      return "degraded";
    case "unset":
      return "missing";
    default:
      return "unavailable";
  }
}

const SYSTEM_ENV_GROUPS: Array<Omit<SystemEnvGroup, "entries">> = [
  {
    key: "host",
    label: "Host context",
    description: "Operating system, user profile, shell, terminal, and machine identity.",
  },
  {
    key: "filesystem",
    label: "Filesystem",
    description: "Executable search paths, caches, configuration roots, and working directories.",
  },
  {
    key: "credentials",
    label: "Credentials",
    description: "Authentication and secret-bearing variables shown only through redacted values.",
  },
  {
    key: "toolchains",
    label: "Toolchains",
    description: "Language runtimes, compilers, SDKs, and package manager configuration.",
  },
  {
    key: "process",
    label: "Process state",
    description: "Application-specific switches and uncategorized values inherited at launch.",
  },
];

function groupSystemEntries(entries: EnvEntry[]): SystemEnvGroup[] {
  const grouped = new Map<SystemEnvFamily, EnvEntry[]>();
  for (const entry of entries) {
    const family = systemEnvironmentFamily(entry);
    const group = grouped.get(family) ?? [];
    group.push(entry);
    grouped.set(family, group);
  }

  return SYSTEM_ENV_GROUPS.map((definition) => ({
    ...definition,
    entries: (grouped.get(definition.key) ?? []).sort((left, right) =>
      left.name.localeCompare(right.name),
    ),
  })).filter((group) => group.entries.length > 0);
}

function systemEnvironmentFamily(entry: EnvEntry): SystemEnvFamily {
  const name = entry.name.toUpperCase();
  if (isSensitiveEnvironmentEntry(entry)) return "credentials";
  if (
    entry.is_path ||
    /(?:^|_)(?:PATH|HOME|ROOT|DIR|DIRECTORY|CACHE|CONFIG|DATA|TEMP|TMP)$/.test(name)
  ) {
    return "filesystem";
  }
  if (
    /^(?:PYTHON|PIP|UV|NODE|NPM|PNPM|BUN|DENO|DOTNET|JAVA|JDK|RUST|CARGO|GO|GOPATH|RUBY|GEM|PHP|COMPOSER|MSBUILD|VCPKG|CONDA)/.test(
      name,
    )
  ) {
    return "toolchains";
  }
  if (
    /^(?:OS|USER|USERNAME|USERDOMAIN|COMPUTERNAME|HOSTNAME|PROCESSOR|NUMBER_OF_PROCESSORS|SHELL|COMSPEC|TERM|SESSIONNAME|WINDIR|SYSTEMROOT|PROGRAMDATA|APPDATA|LOCALAPPDATA)$/.test(
      name,
    )
  ) {
    return "host";
  }
  return "process";
}

function isSensitiveEnvironmentEntry(entry: EnvEntry) {
  return /(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL|AUTH|COOKIE|SESSION)/i.test(
    entry.name,
  );
}

function systemEntryLabel(entry: EnvEntry) {
  if (isSensitiveEnvironmentEntry(entry)) return "redacted";
  if (entry.is_path) return "path";
  return "value";
}

function systemEntryVariant(entry: EnvEntry): StatePillVariant {
  if (isSensitiveEnvironmentEntry(entry)) return "degraded";
  if (entry.is_path) return "ok";
  return "unavailable";
}

function environmentEntryRole(entry: EnvEntry) {
  if (isSensitiveEnvironmentEntry(entry)) return "Protected process credential";
  if (entry.is_path) return "Inherited filesystem location";
  return "Inherited process value";
}
