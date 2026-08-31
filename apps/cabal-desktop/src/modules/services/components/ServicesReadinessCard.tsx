// Left card of the Services console top row: donut gauge of ready-vs-total services plus a
// caption naming any services that need attention — derived from real degraded/not-set-up rows.
import type { ServiceRow } from "@/api/operations";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { Gauge } from "@/components/Gauge";
import { RefreshButton } from "@/components/RefreshButton";
import { attentionCaption } from "@/modules/services/serviceStatus";

export interface ServicesReadinessCardProps {
  services: ServiceRow[];
  readyCount: number;
  totalCount: number;
  onRefresh: () => void;
  isFetching: boolean;
}

export function ServicesReadinessCard({
  services,
  readyCount,
  totalCount,
  onRefresh,
  isFetching,
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
      <CardRefreshFooter>
        <RefreshButton label="services" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </div>
  );
}
