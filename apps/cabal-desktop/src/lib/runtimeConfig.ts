// Resolves the backend base URL and auth header from the Tauri-injected runtime config, if present.
import { invoke } from "@tauri-apps/api/core";

export interface CabalRuntimeConfig {
  port: number;
  token: string;
}

declare global {
  interface Window {
    __CABAL__?: CabalRuntimeConfig;
    __TAURI_INTERNALS__?: unknown;
  }
}

export class RuntimeConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RuntimeConfigError";
  }
}

function runtimeConfig(): CabalRuntimeConfig | null {
  return typeof window !== "undefined" && window.__CABAL__ !== undefined ? window.__CABAL__ : null;
}

/** True inside the desktop shell, where relative /api URLs cannot resolve. */
export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;
}

/**
 * Ensure window.__CABAL__ is populated before the app issues its first request.
 *
 * The shell's injection is per-page, so a reload arrives with the global unset;
 * asking the Rust side over IPC re-resolves it without waiting for the health
 * monitor to notice a failure.
 */
export async function ensureRuntimeConfig(): Promise<void> {
  if (!isTauriRuntime() || runtimeConfig() !== null) return;
  const config = await invoke<CabalRuntimeConfig | null>("cabal_runtime_config");
  if (config === null || config === undefined) {
    throw new RuntimeConfigError("the cabal backend has not reported a connection yet");
  }
  window.__CABAL__ = config;
}

// Dev/browser mode: relative /api/* through the Vite proxy, which injects auth itself.
// Tauri mode: absolute URL against the injected port, with the token attached by the caller.
export function resolveApiUrl(path: string): string {
  const config = runtimeConfig();
  if (config === null) {
    if (isTauriRuntime()) {
      // Falling back to a relative URL here would fail silently against tauri://.
      throw new RuntimeConfigError(`no backend connection available for ${path}`);
    }
    return path;
  }
  return `http://127.0.0.1:${config.port}${path}`;
}

export function apiAuthHeaders(): Record<string, string> {
  const config = runtimeConfig();
  return config === null ? {} : { Authorization: `Bearer ${config.token}` };
}
