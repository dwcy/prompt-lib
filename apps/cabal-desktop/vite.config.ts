import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type ProxyOptions } from "vite";

interface Handshake {
  port: number;
  token: string;
}

const PROXIED_ROUTES = ["/api", "/brand"] as const;

// Mirrors the backend's platform user-data dir resolution: `platformdirs.user_data_dir("cabal",
// appauthor=False)` defaults to roaming=False, i.e. LOCALAPPDATA on Windows, NOT APPDATA (roaming)
// (see specs/015-web-ui-overhaul/contracts/desktop-shell.contract.md).
function userDataDir(): string {
  if (process.platform === "win32") {
    return process.env.LOCALAPPDATA ?? process.env.APPDATA ?? join(homedir(), "AppData", "Local");
  }
  if (process.platform === "darwin") {
    return join(homedir(), "Library", "Application Support");
  }
  return process.env.XDG_DATA_HOME ?? join(homedir(), ".local", "share");
}

function parseHandshake(raw: string): Handshake | null {
  const data: unknown = JSON.parse(raw);
  if (
    typeof data === "object" &&
    data !== null &&
    "port" in data &&
    "token" in data &&
    typeof data.port === "number" &&
    Number.isInteger(data.port) &&
    typeof data.token === "string"
  ) {
    return { port: data.port, token: data.token };
  }
  return null;
}

// Dev-mode stand-in for the Tauri shell: reads the backend handshake file and
// forwards /api and /brand to the ephemeral backend port. Missing or invalid
// handshake means no proxy — the UI renders its disconnected state.
function handshakeProxy(): Record<string, ProxyOptions> | undefined {
  const handshakePath = join(userDataDir(), "cabal", "webapi-handshake.json");
  if (!existsSync(handshakePath)) {
    console.warn(
      `[cabal-desktop] No backend handshake file at ${handshakePath} — starting dev server ` +
        "without /api and /brand proxies. Start the cabal backend, then restart `pnpm dev`; " +
        "until then the UI shows its disconnected state.",
    );
    return undefined;
  }

  let handshake: Handshake | null;
  try {
    handshake = parseHandshake(readFileSync(handshakePath, "utf8"));
  } catch {
    handshake = null;
  }
  if (handshake === null) {
    console.warn(
      `[cabal-desktop] Handshake file at ${handshakePath} is unreadable or not ` +
        "{ port: number, token: string } — skipping /api and /brand proxies.",
    );
    return undefined;
  }

  const target = `http://127.0.0.1:${handshake.port}`;
  // The browser never sees the token; the dev proxy attaches it, mirroring the
  // shell injecting { port, token } in production (contract: "behavior identical").
  const routeOptions: ProxyOptions = {
    target,
    changeOrigin: true,
    headers: { authorization: `Bearer ${handshake.token}` },
  };
  console.info(`[cabal-desktop] Proxying ${PROXIED_ROUTES.join(", ")} to ${target}`);
  return Object.fromEntries(PROXIED_ROUTES.map((route) => [route, routeOptions]));
}

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    // Only resolved for `vite` dev serve — `vite build` never uses the proxy.
    proxy: command === "serve" ? handshakeProxy() : undefined,
  },
}));
