// T024: .NET codegen module shell — the availability gate (FR-002), the prose change-request and
// new-service forms, the approval gate that replaces them while a plan awaits a decision, and the
// most recently produced run's outcome.

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import type { CodegenAvailabilityReason } from "@/api/codegen";
import { useCodegenAvailability, useCodegenPendingIntent, useCodegenRuns } from "@/api/codegen";
import { queryKeys } from "@/api/queryKeys";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { ApprovalGate } from "@/modules/codegen/components/ApprovalGate";
import { NewServiceForm } from "@/modules/codegen/components/NewServiceForm";
import { RequestForm } from "@/modules/codegen/components/RequestForm";
import { RunOutcome } from "@/modules/codegen/components/RunOutcome";
import { useProjectContextStore } from "@/stores/projectContext";

const AVAILABILITY_COPY: Partial<
  Record<CodegenAvailabilityReason, { title: string; body: string }>
> = {
  no_project_selected: {
    title: "Select a project first",
    body: "The .NET code generator works against a selected project. Choose one to continue.",
  },
  not_a_dotnet_project: {
    title: "Not a .NET project",
    body: "No .csproj or .sln was found under the selected project.",
  },
  subsystem_missing: {
    title: "Code generation subsystem unavailable",
    body: "The dotnetgen CLI or its dependencies could not be found.",
  },
};

export function CodegenModule() {
  const queryClient = useQueryClient();
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  const { navigateToModule } = useModuleNavigation();
  const availability = useCodegenAvailability();
  const pendingQuery = useCodegenPendingIntent();
  const runsQuery = useCodegenRuns();
  const planAction = useAction("codegen.plan");
  const newServiceAction = useAction("codegen.new_service");

  const invalidateCodegen = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.scoped("codegen", projectPath) });
  }, [queryClient, projectPath]);

  useEffect(() => {
    if (planAction.phase !== "succeeded" && newServiceAction.phase !== "succeeded") return;
    invalidateCodegen();
  }, [planAction.phase, newServiceAction.phase, invalidateCodegen]);

  if (availability.isPending) return <EmptyState title="Checking code generation availability…" />;
  if (availability.isError) {
    return (
      <EmptyState title="Could not reach the code generator" body={availability.error.message} />
    );
  }

  if (!availability.data.available) {
    const copy = AVAILABILITY_COPY[availability.data.reason] ?? {
      title: "Code generation unavailable",
      body: availability.data.detail,
    };
    return (
      <EmptyState
        title={copy.title}
        body={availability.data.detail || copy.body}
        action={
          availability.data.reason === "no_project_selected" ? (
            <button type="button" onClick={() => navigateToModule("project_gate")}>
              Choose a project
            </button>
          ) : undefined
        }
      />
    );
  }

  const pending = pendingQuery.data ?? null;
  const latestRun = runsQuery.data?.[0] ?? null;

  return (
    <div className="codegen-module">
      <header className="codegen-module__header">
        <h1>.NET Code Generation</h1>
        <p>Describe a change in prose, or scaffold a new service from a locked template.</p>
      </header>

      {pending !== null ? (
        <ApprovalGate pending={pending} onDecided={invalidateCodegen} />
      ) : (
        <div className="codegen-module__forms">
          <RequestForm
            submitting={planAction.phase === "preparing" || planAction.phase === "executing"}
            onSubmit={(values) =>
              planAction.prepare({ request: values.request, template: values.template })
            }
          />
          <NewServiceForm
            projectPath={projectPath}
            submitting={
              newServiceAction.phase === "preparing" || newServiceAction.phase === "executing"
            }
            onSubmit={(values) =>
              newServiceAction.prepare({
                template: values.template,
                destination: values.destination,
                description: values.description,
              })
            }
          />
        </div>
      )}

      {latestRun !== null ? (
        <section className="codegen-module__latest-run" aria-label="Latest run">
          <h2>Latest run</h2>
          {latestRun.readable ? (
            <>
              <p className="codegen-module__latest-request">{latestRun.request}</p>
              <RunOutcome outcome={latestRun.outcome} />
            </>
          ) : (
            <p className="codegen-module__latest-error" role="alert">
              Could not read this run's record: {latestRun.error}
            </p>
          )}
        </section>
      ) : null}

      <ConfirmDialog action={planAction} actionTitle="Generate plan" />
      <ConfirmDialog action={newServiceAction} actionTitle="Scaffold new service" />

      {planAction.jobId !== null ? <JobPane jobId={planAction.jobId} /> : null}
      {newServiceAction.jobId !== null ? <JobPane jobId={newServiceAction.jobId} /> : null}
    </div>
  );
}
