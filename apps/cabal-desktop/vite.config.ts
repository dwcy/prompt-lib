import { existsSync, readFileSync } from "node:fs";
import { request as httpRequest } from "node:http";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

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
function readHandshake(): Handshake | null {
  const handshakePath =
    process.env.PROMPTLIB_CABAL_HANDSHAKE_PATH ??
    join(userDataDir(), "cabal", "webapi-handshake.json");
  if (!existsSync(handshakePath)) {
    return null;
  }

  try {
    return parseHandshake(readFileSync(handshakePath, "utf8"));
  } catch {
    return null;
  }
}

function handshakeProxyPlugin(): Plugin {
  return {
    name: "cabal-handshake-proxy",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = request.url ?? "";
        const shouldProxy = PROXIED_ROUTES.some(
          (route) => path === route || path.startsWith(`${route}/`) || path.startsWith(`${route}?`),
        );
        if (!shouldProxy) {
          next();
          return;
        }

        const handshake = readHandshake();
        if (handshake === null) {
          response.statusCode = 502;
          response.end("Cabal backend handshake unavailable");
          return;
        }

        const proxyHeaders = {
          ...request.headers,
          host: `127.0.0.1:${handshake.port}`,
          authorization: `Bearer ${handshake.token}`,
        };
        if (process.env.PROMPTLIB_CABAL_HANDSHAKE_PATH !== undefined) {
          delete proxyHeaders.origin;
        }

        const proxyRequest = httpRequest(
          {
            hostname: "127.0.0.1",
            port: handshake.port,
            path,
            method: request.method,
            headers: proxyHeaders,
          },
          (proxyResponse) => {
            response.writeHead(proxyResponse.statusCode ?? 502, proxyResponse.headers);
            proxyResponse.pipe(response);
          },
        );
        proxyRequest.on("error", () => {
          if (!response.headersSent) response.statusCode = 502;
          response.end("Cabal backend unavailable");
        });
        request.pipe(proxyRequest);
      });
    },
  };
}

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss(), ...(command === "serve" ? [handshakeProxyPlugin()] : [])],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    watch: {
      ignored: ["**/src-tauri/target/**"],
    },
  },
}));
