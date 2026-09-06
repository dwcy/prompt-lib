// Dispatches to the per-section content builder and re-exports the shared shapes.
import type { DashboardSectionKey } from "@/api/dashboard";
import type { UnknownSection } from "@/lib/unknownFields";
import { buildAzureDevOpsContent } from "@/modules/project-dashboard/sectionContent/azureDevops";
import { buildGitContent } from "@/modules/project-dashboard/sectionContent/git";
import { buildGithubContent } from "@/modules/project-dashboard/sectionContent/github";
import { buildSupabaseContent } from "@/modules/project-dashboard/sectionContent/supabase";
import type { SectionContent } from "@/modules/project-dashboard/sectionContent/types";
import { buildVercelContent } from "@/modules/project-dashboard/sectionContent/vercel";

export type {
  HealthFact,
  HealthFactItem,
  HealthLink,
  SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

export function buildSectionContent(
  sectionKey: DashboardSectionKey,
  section: UnknownSection,
): SectionContent {
  switch (sectionKey) {
    case "git":
      return buildGitContent(section);
    case "github":
      return buildGithubContent(section);
    case "supabase":
      return buildSupabaseContent(section);
    case "azure_devops":
      return buildAzureDevOpsContent(section);
    case "vercel":
      return buildVercelContent(section);
  }
}
