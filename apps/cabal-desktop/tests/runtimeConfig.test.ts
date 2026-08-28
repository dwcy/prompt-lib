// Unit test: the desktop shell's runtime config must survive a reload, and its absence
// must fail loudly instead of silently falling back to unresolvable relative URLs.
import { afterEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

import {
  ensureRuntimeConfig,
  resolveApiUrl,
  RuntimeConfigError,
} from "@/lib/runtimeConfig";

afterEach(() => {
  invokeMock.mockReset();
  window.__CABAL__ = undefined;
  window.__TAURI_INTERNALS__ = undefined;
});

describe("runtime config", () => {
  it("re-resolves the connection over IPC when a reload wiped the injected global", async () => {
    window.__TAURI_INTERNALS__ = {};
    invokeMock.mockResolvedValue({ port: 51234, token: "reload-token" });

    await ensureRuntimeConfig();

    expect(resolveApiUrl("/api/health")).toBe("http://127.0.0.1:51234/api/health");
  });

  it("reports a missing backend connection instead of returning a relative URL", () => {
    window.__TAURI_INTERNALS__ = {};

    expect(() => resolveApiUrl("/api/health")).toThrow(RuntimeConfigError);
  });

  it("keeps relative URLs in the browser dev server, where the proxy handles auth", () => {
    expect(resolveApiUrl("/api/health")).toBe("/api/health");
  });
});
