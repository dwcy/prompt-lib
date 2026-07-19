// Display labels for the four Project Dashboard sections (git/github/supabase/vercel).
import type { DashboardSectionKey } from "@/api/dashboard";

export const DASHBOARD_SECTION_LABELS: Record<DashboardSectionKey, string> = {
  git: "Git",
  github: "GitHub",
  supabase: "Supabase",
  vercel: "Vercel",
};

export const DASHBOARD_SECTION_ROLES: Record<DashboardSectionKey, string> = {
  git: "Repository state",
  github: "Remote collaboration",
  supabase: "Data platform",
  vercel: "Delivery target",
};
