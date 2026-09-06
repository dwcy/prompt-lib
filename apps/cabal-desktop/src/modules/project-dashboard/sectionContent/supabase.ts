// Supabase section content: project status/region/plan facts plus dashboard/schema links.
import { readString, type UnknownSection } from "@/lib/unknownFields";
import {
  type HealthFact,
  type HealthLink,
  NO_SUMMARY,
  type SectionContent,
} from "@/modules/project-dashboard/sectionContent/types";

export function buildSupabaseContent(section: UnknownSection): SectionContent {
  const projectRef = readString(section, ["project_ref"]);
  const status = readString(section, ["status"]);
  const region = readString(section, ["region"]);
  const plan = readString(section, ["plan_name"]);
  const dbLocation = readString(section, ["db_location"]);
  const lastMigration = readString(section, ["last_migration"]);
  const lastBackup = readString(section, ["last_backup"]);
  const dashboardUrl = readString(section, ["dashboard_url"]);
  const schemaUrl = readString(section, ["schema_visualizer_url"]);

  const facts: HealthFact[] = [];
  if (status !== null) facts.push({ label: "Status", value: status });
  if (region !== null) facts.push({ label: "Region", value: region });
  if (plan !== null) facts.push({ label: "Plan", value: plan });
  if (dbLocation !== null) facts.push({ label: "DB location", value: dbLocation });
  if (lastMigration !== null) facts.push({ label: "Last migration", value: lastMigration });
  if (lastBackup !== null) facts.push({ label: "Last backup", value: lastBackup });

  const links: HealthLink[] = [];
  if (dashboardUrl !== null) links.push({ label: "Dashboard", url: dashboardUrl });
  if (schemaUrl !== null) links.push({ label: "Schema visualizer", url: schemaUrl });

  return {
    summary:
      projectRef !== null
        ? status !== null
          ? `${projectRef} · ${status}`
          : projectRef
        : NO_SUMMARY,
    facts,
    links,
  };
}
