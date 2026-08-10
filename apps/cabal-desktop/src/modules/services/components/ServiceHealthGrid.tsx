// Right side of the Services console top row: a 2-up grid of per-service health cards.
import type { ServiceRow } from "@/api/operations";
import { StatePill } from "@/components/StatePill";
import { serviceFixHint, serviceVariant } from "@/modules/services/serviceStatus";

export interface ServiceHealthGridProps {
  services: ServiceRow[];
}

export function ServiceHealthGrid({ services }: ServiceHealthGridProps) {
  return (
    <div className="svc-health-grid">
      {services.map((service) => (
        <ServiceHealthCard key={service.key} service={service} />
      ))}
    </div>
  );
}

interface ServiceHealthCardProps {
  service: ServiceRow;
}

function ServiceHealthCard({ service }: ServiceHealthCardProps) {
  const fixHint = serviceFixHint(service);
  return (
    <article className={`svc-health-card svc-health-card--${service.state}`}>
      <header className="svc-health-card__header">
        <span className={`svc-dot svc-dot--${service.state}`} aria-hidden="true" />
        <strong>{service.label}</strong>
        <StatePill variant={serviceVariant(service.state)} label={service.state} />
      </header>
      <p className="svc-health-card__summary">{service.description}</p>
      {fixHint !== null ? <p className="svc-health-card__fix">{`→ ${fixHint}`}</p> : null}
    </article>
  );
}
