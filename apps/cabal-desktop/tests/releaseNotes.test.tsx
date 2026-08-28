// Component test: the Release news page lists the shipped features, filters by section and
// search, and its sidebar locations stay in step with the modules that actually exist.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MODULE_GROUP_LABELS, MODULE_NAV_LABELS } from "@/modules/registry";
import { ReleaseNotesModule } from "@/modules/release-notes/ReleaseNotesModule";
import { RELEASE_SECTIONS } from "@/modules/release-notes/releaseNotes";

const NAV_LOCATION = /^(?<group>[^→]+) → (?<screen>.+)$/;

describe("Release news", () => {
  it("shows every documented feature grouped under its section", () => {
    render(<ReleaseNotesModule />);

    for (const section of RELEASE_SECTIONS) {
      expect(screen.getByRole("heading", { name: section.title })).toBeInTheDocument();
    }
  });

  it("narrows to a single section when one is selected", async () => {
    const user = userEvent.setup();
    render(<ReleaseNotesModule />);

    await user.click(screen.getByRole("button", { name: "Machine" }));

    expect(screen.getByRole("heading", { name: "Tools catalog" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Knowledge and retrieval" })).toBeNull();
  });

  it("finds a feature by what the reader is trying to do", async () => {
    const user = userEvent.setup();
    render(<ReleaseNotesModule />);

    await user.type(screen.getByRole("searchbox"), "vulnerab");

    expect(screen.getByRole("heading", { name: "Package security" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Tools catalog" })).toBeNull();
  });

  it("reports when nothing matches instead of rendering an empty page", async () => {
    const user = userEvent.setup();
    render(<ReleaseNotesModule />);

    await user.type(screen.getByRole("searchbox"), "no-such-feature");

    expect(screen.getByText("Nothing matches that search")).toBeInTheDocument();
  });

  it("only points at sidebar groups and screens that exist", () => {
    const groups = new Set(Object.values(MODULE_GROUP_LABELS));
    const screens = new Set(Object.values(MODULE_NAV_LABELS));

    const broken = RELEASE_SECTIONS.flatMap((section) => section.entries)
      .map((entry) => entry.location.match(NAV_LOCATION)?.groups)
      .filter((match) => match !== undefined)
      .filter((match) => !groups.has(match.group) || !screens.has(match.screen));

    expect(broken).toEqual([]);
  });
});
