// Claude Config console: account identity + config surfaces (left column), doctor warnings + usage
// stats (right column) — bound to /api/account, /api/claude-info, /api/doctor, and /api/sessions,
// per specs/015-web-ui-overhaul/redesign/cabal-console-mock.html (isClaude "Claude Config", ~443-511).
import { useAccount, useClaudeInfo, useDoctor, useSessions } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { ClaudeAccountCard } from "./components/ClaudeAccountCard";
import { ClaudeStatsCard } from "./components/ClaudeStatsCard";
import { ConfigSurfacesCard } from "./components/ConfigSurfacesCard";
import { DoctorWarningsCard } from "./components/DoctorWarningsCard";
import "./AccountModule.css";

export function AccountModule() {
  const accountQuery = useAccount();
  const infoQuery = useClaudeInfo();
  const doctorQuery = useDoctor();
  const sessionsQuery = useSessions("date_desc", null);
  const { navigateToModule } = useModuleNavigation();

  if (accountQuery.isPending || infoQuery.isPending) {
    return <EmptyState title="Loading Claude config…" />;
  }

  if (accountQuery.isError) {
    return <EmptyState title="Could not load account state" body={accountQuery.error.message} />;
  }

  if (infoQuery.isError) {
    return <EmptyState title="Could not load assistant info" body={infoQuery.error.message} />;
  }

  const account = accountQuery.data;
  const info = infoQuery.data;
  const findings = doctorQuery.data?.findings ?? [];

  return (
    <div className="ccfg-console">
      <div className="ccfg-console__column">
        <ClaudeAccountCard
          account={account}
          runtime={info.runtime}
          isRefreshing={accountQuery.isFetching || infoQuery.isFetching}
          onRefresh={() => {
            void accountQuery.refetch();
            void infoQuery.refetch();
          }}
          onOpenModels={() => navigateToModule("model_assignments")}
        />
        <ConfigSurfacesCard
          documents={info.documents}
          onRefresh={() => void infoQuery.refetch()}
          isFetching={infoQuery.isFetching}
        />
      </div>

      <div className="ccfg-console__column">
        {doctorQuery.isSuccess && findings.length > 0 ? (
          <DoctorWarningsCard
            findings={findings}
            onOpenDoctor={() => navigateToModule("doctor")}
            onRefresh={() => void doctorQuery.refetch()}
            isFetching={doctorQuery.isFetching}
          />
        ) : null}
        {sessionsQuery.isSuccess ? (
          <ClaudeStatsCard
            totals={sessionsQuery.data.totals}
            onOpenSessions={() => navigateToModule("sessions")}
            onRefresh={() => void sessionsQuery.refetch()}
            isFetching={sessionsQuery.isFetching}
          />
        ) : null}
      </div>
    </div>
  );
}
