// The views a deploy-tree file can be read in, and which of them a given file supports.
import type { ConfigFile, ConfigFileSide } from "@/api/config";

export type FileViewTab = "diff" | ConfigFileSide;

export const FILE_VIEW_LABELS: Record<FileViewTab, string> = {
  diff: "Diff",
  deployed: "Deployed",
  source: "Repo source",
};

/** Diff first when there is one to read; a file that only exists in the repo opens on source. */
export function initialTab(file: ConfigFile): FileViewTab {
  if (file.diff_available) return "diff";
  return file.state === "new" ? "source" : "deployed";
}

export function availableTabs(file: ConfigFile): FileViewTab[] {
  const sides: FileViewTab[] = ["deployed", "source"];
  return file.diff_available ? ["diff", ...sides] : sides;
}
