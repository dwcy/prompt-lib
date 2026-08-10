// Full-width "Local agent services" table: dot | name | description | meta | state pill | action
// button (Setup/Start/Stop, gated by runnable + prereqs — unchanged confirm-flow behavior).
// Clicking a row's name selects it for the detail panel below; the footer restates the dependency
// graph the old inline dependency-lines strip used to show.
import type { ServiceRow } from "@/api/operations";
import { StatePill } from "@/components/StatePill";
import {
  serviceActionLabel,
  serviceDependencyLines,
  serviceMeta,
  serviceVariant,
} from "@/modules/services/serviceStatus";

export interface LocalAgentServicesTableProps {
  services: ServiceRow[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
  onSetup: (service: ServiceRow) => void;
  onStart: (service: ServiceRow) => void;
  onStop: (service: ServiceRow) => void;
}

export function LocalAgentServicesTable({
  services,
  selectedKey,
  onSelect,
  onSetup,
  onStart,
  onStop,
}: LocalAgentServicesTableProps) {
  const dependencyLines = serviceDependencyLines(services);
  const footer =
    dependencyLines.length === 0 ? "No service dependencies." : dependencyLines.join(" · ");

  return (
    <section className="svc-table" aria-label="Local agent services">
      <header className="svc-table__header">
        <b>Local agent services</b>
        <span>{tableDescription(services)}</span>
      </header>
      <div className="svc-rows">
        {services.map((service) => (
          <ServiceRowItem
            key={service.key}
            service={service}
            isSelected={service.key === selectedKey}
            onSelect={onSelect}
            onSetup={onSetup}
            onStart={onStart}
            onStop={onStop}
          />
        ))}
      </div>
      <footer className="svc-table__footer">{footer}</footer>
    </section>
  );
}

function tableDescription(services: ServiceRow[]): string {
  if (services.length === 0) return "No local agent services configured.";
  return `${services.map((service) => service.key).join(" · ")} — run from one place instead of remembering CLI commands.`;
}

interface ServiceRowItemProps {
  service: ServiceRow;
  isSelected: boolean;
  onSelect: (key: string) => void;
  onSetup: (service: ServiceRow) => void;
  onStart: (service: ServiceRow) => void;
  onStop: (service: ServiceRow) => void;
}

function ServiceRowItem({
  service,
  isSelected,
  onSelect,
  onSetup,
  onStart,
  onStop,
}: ServiceRowItemProps) {
  const prereqsReady = service.prereqs.every((item) => item.ok);
  const actionLabel = serviceActionLabel(service, prereqsReady);

  return (
    <div className={`svc-row${isSelected ? " is-selected" : ""}`}>
      <span className={`svc-dot svc-dot--${service.state}`} aria-hidden="true" />
      <button
        type="button"
        className="svc-row__name"
        aria-pressed={isSelected}
        onClick={() => onSelect(service.key)}
      >
        {service.key}
      </button>
      <span className="svc-row__desc">{service.description}</span>
      <span className="svc-row__meta">{serviceMeta(service)}</span>
      <StatePill variant={serviceVariant(service.state)} label={service.state} />
      <span className="svc-row__action">
        {actionLabel === "Setup" ? (
          <button type="button" onClick={() => onSetup(service)}>
            Setup
          </button>
        ) : actionLabel === "Start" ? (
          <button type="button" onClick={() => onStart(service)}>
            Start
          </button>
        ) : actionLabel === "Stop" ? (
          <button type="button" className="svc-row__action--danger" onClick={() => onStop(service)}>
            Stop
          </button>
        ) : null}
      </span>
    </div>
  );
}
