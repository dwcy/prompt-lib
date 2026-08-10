// Left card of the Services console top row: donut gauge of ready-vs-total services plus a
// caption naming any services that need attention — derived from real degraded/not-set-up rows.
import type { ServiceRow } from "@/api/operations";
import { Gauge } from "@/components/Gauge";
import { attentionCaption } from "@/modules/services/serviceStatus";

export interface ServicesReadinessCardProps {
  services: ServiceRow[];
  readyCount: number;
  totalCount: number;
}

export function ServicesReadinessCard({
  services,
  readyCount,
  totalCount,
}: ServicesReadinessCardProps) {
  const attention = services.filter(
    (service) => service.state === "blocked" || service.state === "not_set_up",
  );
  const fraction = totalCount > 0 ? readyCount / totalCount : 0;

  return (
    <div className="svc-readiness">
      <Gauge
        fraction={fraction}
        value={`${readyCount}/${totalCount}`}
        caption="services ready"
        size={150}
        tone={attention.length === 0 ? "ok" : "warning"}
      />
      <p className="svc-readiness__caption">{attentionCaption(attention)}</p>
    </div>
  );
}
