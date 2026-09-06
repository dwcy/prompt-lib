import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { EnvEntry } from "@/api/securityEnvironment";
import { EnvTable, type EnvTableRow } from "@/modules/environment/components/EnvTable";
import { EnvironmentModule } from "@/modules/environment/EnvironmentModule";
import { sourceLabel, sourceVariant } from "@/modules/environment/environmentPresentation";
import { requireModule } from "@/modules/registry";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function entry(overrides: Partial<EnvEntry> = {}): EnvEntry {
  return {
    name: "PROJECTS_PATH",
    value_redacted: "C:/projects",
    default: "C:/projects",
    is_path: true,
    source: "system",
    editable: true,
    description: "Project workspace root",
    ...overrides,
  };
}

function row(overrides: Partial<EnvTableRow> = {}): EnvTableRow {
  return {
    entry: entry(),
    value: "C:/projects",
    isOn: true,
    canToggle: true,
    editing: false,
    dirty: false,
    isSecret: false,
    stateVariant: "ok",
    stateLabel: "set",
    onToggle: () => undefined,
    ...overrides,
  };
}

describe("Environment console presentation", () => {
  it("groups Environment under Machine navigation", () => {
    expect(requireModule("environment").group).toBe("machine");
  });

  it("uses the design state labels and semantic colors", () => {
    expect(sourceLabel("system")).toBe("set");
    expect(sourceLabel("unset")).toBe("missing");
    expect(sourceVariant("system")).toBe("ok");
    expect(sourceVariant("default")).toBe("unavailable");
    expect(sourceVariant("unset")).toBe("missing");
  });

  it("identifies and masks a secret without rendering its raw value", () => {
    const secretEntry = entry({
      name: "FIGMA_ACCESS_TOKEN",
      value_redacted: "figd-raw-secret",
      is_path: false,
    });
    render(
      <EnvTable
        ariaLabel="Environment variables"
        rows={[
          row({
            entry: secretEntry,
            value: secretEntry.value_redacted,
            isSecret: true,
            stateVariant: "ok",
            stateLabel: "set",
          }),
        ]}
      />,
    );

    expect(screen.getByRole("columnheader", { name: /secret/i })).toBeInTheDocument();
    expect(screen.getByText("secret")).toHaveAttribute("title", "Secret value; masked");
    expect(screen.getByText("••••••••••••")).toBeInTheDocument();
    expect(screen.queryByText("figd-raw-secret")).not.toBeInTheDocument();
    expect(screen.getByText("set")).toHaveAttribute("data-state", "ok");
  });

  it("uses an accessible eye control to reveal and hide an edited secret", async () => {
    const user = userEvent.setup();
    const secretEntry = entry({ name: "API_KEY", is_path: false });
    render(
      <EnvTable
        ariaLabel="Environment variables"
        rows={[
          row({
            entry: secretEntry,
            value: "raw-secret",
            editing: true,
            isSecret: true,
          }),
        ]}
      />,
    );

    const input = screen.getByLabelText("API_KEY value");
    expect(input).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Show API_KEY secret" }));
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide API_KEY secret" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Hide API_KEY secret" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("lets an unset secret switch on so its value can be entered", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/env", () =>
        HttpResponse.json(
          wrapEnvelope({
            scope: "curated" as const,
            entries: [
              entry({
                name: "OBSIDIAN_API_KEY",
                value_redacted: "",
                default: "",
                is_path: false,
                source: "unset",
                description: "Obsidian Local REST API key",
              }),
            ],
            count: 1,
            editable_count: 1,
            platform: "windows",
          }),
        ),
      ),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <EnvironmentModule />
      </QueryClientProvider>,
    );

    const toggle = await screen.findByRole("switch", { name: "Toggle OBSIDIAN_API_KEY" });
    expect(toggle).toHaveAttribute("aria-checked", "false");

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-checked", "true");
    const secretInput = screen.getByLabelText("OBSIDIAN_API_KEY value");
    expect(secretInput).toHaveAttribute("type", "password");

    await user.type(secretInput, "test-secret");
    expect(screen.getByRole("button", { name: "Apply 1" })).toBeEnabled();
  });
});
