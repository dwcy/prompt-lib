// Resolves the help text for a module from the release notes, matching on the sidebar path each
// entry already records ("Machine → Overview"). Deliberately derives that path from the nav
// constants rather than storing a second module->docs table: one copy of the content, and a
// renamed group or nav label can only ever produce a miss, which moduleDocs.test.tsx catches.

import {
  MODULE_GROUP_LABELS,
  MODULE_NAV_LABELS,
  type ModuleKey,
  requireModule,
} from "@/modules/registry";
import { RELEASE_SECTIONS, type ReleaseEntry } from "@/modules/release-notes/releaseNotes";

const LOCATION_SEPARATOR = " → ";

/** The sidebar path shown in the release notes for `key`, e.g. "Machine → Overview". */
export function moduleLocationPath(key: ModuleKey): string {
  const group = requireModule(key).group;
  return `${MODULE_GROUP_LABELS[group]}${LOCATION_SEPARATOR}${MODULE_NAV_LABELS[key]}`;
}

/** Every release-note entry documenting `key`, in the order the release notes present them. */
export function moduleDocEntries(key: ModuleKey): ReleaseEntry[] {
  const path = moduleLocationPath(key);
  const entries = RELEASE_SECTIONS.flatMap((section) => section.entries);
  return entries.filter((entry) => entry.location === path);
}
