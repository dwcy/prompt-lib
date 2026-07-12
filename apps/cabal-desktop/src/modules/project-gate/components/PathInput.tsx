// Path entry for the project gate: native folder picker via @tauri-apps/plugin-dialog when running
// inside the Tauri shell, otherwise a plain text input for dev-in-browser mode (Vite) where no
// Tauri runtime exists to answer the dialog invoke.
import { type FormEvent, useState } from "react";

export interface PathInputProps {
  onSubmit: (path: string) => void;
  disabled?: boolean;
}

// Mirrors @tauri-apps/api/core's own `isTauri()` (`!!(globalThis || window).isTauri`) — inlined so
// the synchronous render decision (show "Browse…" or not) doesn't need an async plugin import.
function isTauriRuntime(): boolean {
  const globalWithTauriFlag = globalThis as { isTauri?: boolean };
  return globalWithTauriFlag.isTauri === true;
}

export function PathInput({ onSubmit, disabled = false }: PathInputProps) {
  const [path, setPath] = useState("");
  const [browseError, setBrowseError] = useState<string | null>(null);

  async function handleBrowse(): Promise<void> {
    setBrowseError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") setPath(selected);
    } catch {
      setBrowseError("Native folder picker failed — enter the path manually.");
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmed = path.trim();
    if (trimmed.length === 0) return;
    onSubmit(trimmed);
  }

  return (
    <form className="project-gate__path-form" onSubmit={handleSubmit}>
      <label className="project-gate__path-label select-none" htmlFor="project-gate-path">
        Project folder path
      </label>
      <div className="project-gate__path-row">
        <input
          id="project-gate-path"
          type="text"
          className="project-gate__path-input"
          value={path}
          onChange={(event) => setPath(event.target.value)}
          placeholder="/path/to/project"
          disabled={disabled}
        />
        {isTauriRuntime() ? (
          <button type="button" onClick={() => void handleBrowse()} disabled={disabled}>
            Browse…
          </button>
        ) : null}
        <button type="submit" disabled={disabled || path.trim().length === 0}>
          Open
        </button>
      </div>
      {browseError !== null ? (
        <p className="project-gate__path-error" role="alert">
          {browseError}
        </p>
      ) : null}
    </form>
  );
}
