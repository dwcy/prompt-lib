import type { ReactNode } from "react";
import type { SystemOverview, TerminalApplication, TerminalShell } from "@/api/systemOverview";

export interface TerminalPanelProps {
  state: SystemOverview | undefined;
  isPending: boolean;
  error: string | null;
}

export function TerminalPanel({ state, isPending, error }: TerminalPanelProps) {
  if (isPending) {
    return (
      <section className="overview-terminal-panel" aria-label="Terminal settings">
        <p className="overview-terminal-panel__message">Reading terminal settings…</p>
      </section>
    );
  }
  if (error !== null || state === undefined) {
    return (
      <section className="overview-terminal-panel" aria-label="Terminal settings">
        <p className="overview-terminal-panel__message overview-terminal-panel__message--error">
          Terminal information is unavailable{error ? `: ${error}` : "."}
        </p>
      </section>
    );
  }

  const shells = state.terminal.shells.filter((shell) => shell.installed);
  const applications = state.terminal.applications.filter((application) => application.installed);

  return (
    <section className="overview-terminal-panel" aria-label="Terminal settings">
      <header className="overview-terminal-panel__header">
        <span className="overview-terminal-panel__icon" aria-hidden="true">
          <TerminalIcon />
        </span>
        <span>
          <strong>Terminal</strong>
          <small>
            Default terminal: {state.terminal.default_terminal ?? "not detected"}
            {state.terminal.default_profile
              ? ` · Default profile: ${state.terminal.default_profile}`
              : ""}
          </small>
        </span>
      </header>

      <div className="overview-terminal-panel__grid">
        <TerminalGroup title={`Shells (${shells.length})`}>
          {shells.length > 0 ? (
            shells.map((shell) => <ShellRow key={shell.key} shell={shell} />)
          ) : (
            <EmptyRow label="No shells detected" />
          )}
        </TerminalGroup>

        <TerminalGroup title={`Terminal apps (${applications.length})`}>
          {applications.length > 0 ? (
            applications.map((application) => (
              <ApplicationRow key={application.key} application={application} />
            ))
          ) : (
            <EmptyRow label="No terminal apps detected" />
          )}
        </TerminalGroup>

        <TerminalGroup title={`Modifications (${state.terminal.modifications.length})`}>
          {state.terminal.modifications.length > 0 ? (
            state.terminal.modifications.map((modification) => (
              <li key={modification.key} title={modification.source}>
                <i aria-hidden="true" />
                <span>
                  <b>{modification.label}</b>
                  <small>{modification.detail}</small>
                </span>
                <code>{modification.kind}</code>
              </li>
            ))
          ) : (
            <EmptyRow label="No customizations detected" />
          )}
        </TerminalGroup>
      </div>
    </section>
  );
}

function TerminalGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="overview-terminal-group">
      <h3>{title}</h3>
      <ul>{children}</ul>
    </div>
  );
}

function ShellRow({ shell }: { shell: TerminalShell }) {
  const title = [shell.path, shell.profile_path].filter(Boolean).join("\n");
  return (
    <li title={title || shell.label}>
      <i aria-hidden="true" />
      <span>
        <b>{shell.label}</b>
        <small>{shortVersion(shell.version)}</small>
      </span>
      {shell.active ? <code>active</code> : shell.configured ? <code>profile</code> : null}
    </li>
  );
}

function ApplicationRow({ application }: { application: TerminalApplication }) {
  const title = [application.path, application.settings_path].filter(Boolean).join("\n");
  return (
    <li title={title || application.label}>
      <i aria-hidden="true" />
      <span>
        <b>{application.label}</b>
        <small>{shortVersion(application.version)}</small>
      </span>
      {application.active ? (
        <code>active</code>
      ) : application.configured ? (
        <code>configured</code>
      ) : null}
    </li>
  );
}

function EmptyRow({ label }: { label: string }) {
  return (
    <li className="overview-terminal-group__empty">
      <span>{label}</span>
    </li>
  );
}

function shortVersion(value: string | null): string {
  if (!value) return "Installed";
  const match = value.match(/v?\d+\.\d+(?:\.\d+)?(?:[-+.][\w.-]+)?/);
  return match?.[0] ?? value;
}

function TerminalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="m7 9 3 3-3 3m5 0h5" />
    </svg>
  );
}
