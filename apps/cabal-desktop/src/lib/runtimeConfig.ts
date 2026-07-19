// Resolves the backend base URL and auth header from the Tauri-injected runtime config, if present.
export interface CabalRuntimeConfig {
  port: number;
  token: string;
}

declare global {
  interface Window {
    __CABAL__?: CabalRuntimeConfig;
  }
}

function runtimeConfig(): CabalRuntimeConfig | null {
  return typeof window !== "undefined" && window.__CABAL__ !== undefined ? window.__CABAL__ : null;
}

// Dev/browser mode: relative /api/* through the Vite proxy, which injects auth itself.
// Tauri mode: absolute URL against the injected port, with the token attached by the caller.
export function resolveApiUrl(path: string): string {
  const config = runtimeConfig();
  return config === null ? path : `http://127.0.0.1:${config.port}${path}`;
}

export function apiAuthHeaders(): Record<string, string> {
  const config = runtimeConfig();
  return config === null ? {} : { Authorization: `Bearer ${config.token}` };
}
