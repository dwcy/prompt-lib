// Maps every nav module to a vendored lucide-animated icon. The icon files under this directory are
// pulled verbatim from https://lucide-animated.com/r/<name>.json (shadcn registry) and are kept
// unedited so re-running `pnpm dlx shadcn@latest add` stays a no-op diff.
import type { ForwardRefExoticComponent, HTMLAttributes, RefAttributes } from "react";
import { BookTextIcon } from "@/components/icons/book-text";
import { BrainIcon } from "@/components/icons/brain";
import { CalendarCogIcon } from "@/components/icons/calendar-cog";
import { CircleDollarSignIcon } from "@/components/icons/circle-dollar-sign";
import { CpuIcon } from "@/components/icons/cpu";
import { FingerprintIcon } from "@/components/icons/fingerprint";
import { FolderCodeIcon } from "@/components/icons/folder-code";
import { FolderCogIcon } from "@/components/icons/folder-cog";
import { FolderSyncIcon } from "@/components/icons/folder-sync";
import { GithubIcon } from "@/components/icons/github";
import { HeartPulseIcon } from "@/components/icons/heart-pulse";
import { HistoryIcon } from "@/components/icons/history";
import { LayoutGridIcon } from "@/components/icons/layout-grid";
import { PartyPopperIcon } from "@/components/icons/party-popper";
import { PlugZapIcon } from "@/components/icons/plug-zap";
import { RadioTowerIcon } from "@/components/icons/radio-tower";
import { RocketIcon } from "@/components/icons/rocket";
import { ServerCogIcon } from "@/components/icons/server-cog";
import { SettingsIcon } from "@/components/icons/settings";
import { ShieldCheckIcon } from "@/components/icons/shield-check";
import { SparklesIcon } from "@/components/icons/sparkles";
import { StethoscopeIcon } from "@/components/icons/stethoscope";
import { TerminalIcon } from "@/components/icons/terminal";
import { UserRoundCogIcon } from "@/components/icons/user-round-cog";
import { WrenchIcon } from "@/components/icons/wrench";
import type { ModuleKey } from "@/modules/registry";

/** Every vendored icon exposes the same imperative handle, so one alias covers all of them. */
export interface AnimatedIconHandle {
  startAnimation: () => void;
  stopAnimation: () => void;
}

interface AnimatedIconProps extends HTMLAttributes<HTMLDivElement> {
  size?: number;
}

export type AnimatedIcon = ForwardRefExoticComponent<
  AnimatedIconProps & RefAttributes<AnimatedIconHandle>
>;

export const MODULE_ICONS: Record<ModuleKey, AnimatedIcon> = {
  project_gate: FolderSyncIcon,
  home_overview: LayoutGridIcon,
  project_dashboard: HeartPulseIcon,
  tools: WrenchIcon,
  config_deploy: RocketIcon,
  cleanup_restore: HistoryIcon,
  settings: SettingsIcon,
  mcp: PlugZapIcon,
  local_config: FolderCogIcon,
  knowledge: BrainIcon,
  services: ServerCogIcon,
  package_security: ShieldCheckIcon,
  sessions: CircleDollarSignIcon,
  scheduled_tasks: CalendarCogIcon,
  account: UserRoundCogIcon,
  doctor: StethoscopeIcon,
  model_assignments: CpuIcon,
  environment: TerminalIcon,
  git_identity: FingerprintIcon,
  provider: GithubIcon,
  init_wizard: SparklesIcon,
  codex: FolderCodeIcon,
  diagnostics: RadioTowerIcon,
  docs: BookTextIcon,
  release_notes: PartyPopperIcon,
  // Placeholders reusing already-vendored icons. This Record is exhaustive over ModuleKey, so a
  // new module breaks the build until it has one, and the icons here are pulled verbatim from the
  // lucide-animated registry rather than hand-written -- adding a dedicated icon means running
  // `pnpm dlx shadcn@latest add`, which is a deliberate act, not something to fake inline.
  codegen: FolderCodeIcon,
  evals: ShieldCheckIcon,
  news: RadioTowerIcon,
  agent_setup: FolderCogIcon,
};
