// Shared Services console helpers: StatePill variant mapping, fix-hint derivation (real API
// fields only — service.detail, else the first unmet prereq message), runtime meta, dependency
// summary lines, and the setup/start/stop action-label decision — used by the gauge card, health
// grid, table, and detail panel so the state logic lives in one place.
import type { ServiceRow, ServiceState } from "@/api/operations";
import type { StatePillVariant } from "@/components/StatePill";

export function serviceVariant(state: ServiceState): StatePillVariant {
  switch (state) {
    case "running":
      return "ok";
    case "stopped":
      return "unavailable";
    case "not_set_up":
      return "missing";
    case "blocked":
      return "error";
    case "info_only":
      return "degraded";
  }
}

export function serviceFixHint(service: ServiceRow): string | null {
  if (service.detail.trim().length > 0) return service.detail;
  const blocker = service.prereqs.find((item) => !item.ok && item.message.trim().length > 0);
  return blocker?.message ?? null;
}

export function serviceMeta(service: ServiceRow): string {
  if (service.state === "running" && service.pid !== null) return `pid ${service.pid}`;
  if (service.default_port !== null) return `port ${service.default_port}`;
  return "—";
}

export function serviceDependencyLines(services: ServiceRow[]): string[] {
  return services.flatMap((service) =>
    service.depends_on.map((dependency) => `${dependency} -> ${service.key}`),
  );
}

export type ServiceActionLabel = "Setup" | "Start" | "Stop";

export function serviceActionLabel(
  service: ServiceRow,
  prereqsReady: boolean,
): ServiceActionLabel | null {
  if (!service.runnable) return null;
  if (service.state === "not_set_up") return "Setup";
  if (service.state === "stopped" && prereqsReady) return "Start";
  if (service.state === "running") return "Stop";
  return null;
}

export function attentionCaption(attention: ServiceRow[]): string {
  if (attention.length === 0) return "All services are ready.";
  const names = attention.map((service) => service.label);
  const list =
    names.length === 1
      ? names[0]
      : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  const verb = attention.length === 1 ? "needs" : "need";
  return `${list} ${verb} attention.`;
}
