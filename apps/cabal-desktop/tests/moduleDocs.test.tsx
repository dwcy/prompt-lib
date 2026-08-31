// Guards the release-notes -> module mapping: it matches on a sidebar path assembled from the nav
// constants, so renaming a group or nav label without touching releaseNotes.ts would silently
// leave a screen with no help text. That failure has to be loud.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import { ModuleDocsDialog } from "@/components/shell/ModuleDocsDialog";
import { moduleDocEntries, moduleLocationPath } from "@/components/shell/moduleDocs";
import { MODULE_REGISTRY, requireModule } from "@/modules/registry";
import { useProjectContextStore } from "@/stores/projectContext";
import { useUiPrefsStore } from "@/stores/uiPrefs";
import { server } from "./msw/server";

// Release news is the page that lists the walkthroughs, so it documents no screen of its own.
const UNDOCUMENTED = new Set(["release_notes"]);

describe("moduleDocs", () => {
  it("finds help text for every documented module", () => {
    const documented = MODULE_REGISTRY.filter((module) => !UNDOCUMENTED.has(module.key));

    const withoutEntries = documented
      .filter((module) => moduleDocEntries(module.key).length === 0)
      .map((module) => `${module.key} (looked for "${moduleLocationPath(module.key)}")`);

    expect(withoutEntries).toEqual([]);
  });

  it("keeps each module's help text to its own sidebar path", () => {
    const toolsEntries = moduleDocEntries("tools");

    expect(toolsEntries.every((entry) => entry.location === "Machine → Tools")).toBe(true);
  });
});

describe("ModuleDocsDialog", () => {
  function renderDialog(onClose = () => {}) {
    const queryClient = new QueryClient();
    return render(
      <QueryClientProvider client={queryClient}>
        <ModuleDocsDialog moduleKey="diagnostics" onClose={onClose} />
      </QueryClientProvider>,
    );
  }

  it("shows the module's summary and its walkthrough steps", () => {
    renderDialog();

    const [entry] = moduleDocEntries("diagnostics");
    expect(screen.getByRole("dialog")).toHaveTextContent(entry.purpose);
  });

  it("closes when the user presses Escape", async () => {
    const user = userEvent.setup();
    let closed = false;
    renderDialog(() => {
      closed = true;
    });

    await user.keyboard("{Escape}");

    expect(closed).toBe(true);
  });
});

describe("header docs affordance", () => {
  beforeEach(() => {
    useProjectContextStore.setState({
      selected: { name: "prompt-lib", path: "C:/projects/prompt-lib" },
      recents: [],
    });
    useUiPrefsStore.setState({ lastModule: "tools" });
    server.use(
      http.get("/api/health", () =>
        HttpResponse.json({
          schema_version: "cabal-web.v2",
          captured_at: "2026-01-01T00:00:00Z",
          status: "ok",
          source: "system",
          stale: false,
          precondition_digest: null,
          data: { version: "0.0.0-test", started_at: "2026-01-01T00:00:00Z", modules: [] },
          error: null,
        }),
      ),
    );
  });

  it("opens the active module's help from the header", async () => {
    const user = userEvent.setup();
    const tools = requireModule("tools");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: `About ${tools.title}` }));

    expect(screen.getByRole("dialog")).toHaveTextContent(moduleDocEntries("tools")[0].purpose);
  });
});
