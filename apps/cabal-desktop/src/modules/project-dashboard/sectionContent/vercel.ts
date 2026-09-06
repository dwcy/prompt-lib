// Vercel section content: plan/region/deployment facts plus dashboard/deployment links.
import { readString, type UnknownSection } from "@/lib/unknownFields";
import {
  type HealthFact,
  type HealthLink,
  NO_SUMMARY,
  type SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

export function buildVercelContent(section: UnknownSection): SectionContent {
  const projectName = readString(section, ["project_name"]);
  const plan = readString(section, ["team_plan"]);
  const region = readString(section, ["region"]);
  const deploymentStatus = readString(section, ["latest_deployment_status"]);
  const dashboardUrl = readString(section, ["dashboard_url"]);
  const deploymentUrl = readString(section, ["latest_deployment_url"]);

  const facts: HealthFact[] = [];
  if (plan !== null) facts.push({ label: "Plan", value: plan });
  if (region !== null) facts.push({ label: "Region", value: region });
  if (deploymentStatus !== null)
    facts.push({ label: "Latest deployment", value: deploymentStatus });

  const links: HealthLink[] = [];
  if (dashboardUrl !== null) links.push({ label: "Dashboard", url: dashboardUrl });
  if (deploymentUrl !== null) links.push({ label: "Latest deployment", url: deploymentUrl });

  return {
    summary:
      projectName !== null
        ? deploymentStatus !== null
          ? `${projectName} · ${deploymentStatus}`
          : projectName
        : NO_SUMMARY,
    facts,
    links,
  };
}
