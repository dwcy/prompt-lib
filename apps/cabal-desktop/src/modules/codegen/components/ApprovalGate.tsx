// T025: the approval-gate view — the plan's intended file changes, explicit approve/reject
// controls, and a stale-plan banner. Never proceeds on timeout or navigation: both decisions are
// discrete button clicks, and a stale plan disables approval rather than silently re-planning.
import { useEffect } from "react";
import type { CodegenIntentFileChange, CodegenPendingIntent } from "@/api/codegen";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { JobPane } from "@/components/JobPane";
import { useAction } from "@/hooks/useAction";

export interface ApprovalGateProps {
  pending: CodegenPendingIntent;
  /** Called once, after approve or reject succeeds, so the caller can refresh pending/run queries. */
  onDecided: () => void;
}

const OPERATION_LABELS: Record<CodegenIntentFileChange["operation"], string> = {
  create: "new file",
  modify: "modified",
  delete: "removed",
};

export function ApprovalGate({ pending, onDecided }: ApprovalGateProps) {
  const approveAction = useAction("codegen.approve");
  const rejectAction = useAction("codegen.reject");

  useEffect(() => {
    if (approveAction.phase === "succeeded" || rejectAction.phase === "succeeded") onDecided();
  }, [approveAction.phase, rejectAction.phase, onDecided]);

  if (approveAction.phase === "succeeded") {
    return (
      <section className="approval-gate approval-gate--approved" aria-label="Approval gate">
        <h2 className="select-none">Approved</h2>
        <p>Writing and verifying the generated code…</p>
        {approveAction.jobId !== null ? <JobPane jobId={approveAction.jobId} /> : null}
      </section>
    );
  }

  if (rejectAction.phase === "succeeded") {
    return (
      <section className="approval-gate approval-gate--rejected" aria-label="Approval gate">
        <h2 className="select-none">Rejected</h2>
        <p>The plan was declined at the gate. Nothing was written.</p>
      </section>
    );
  }

  return (
    <section className="approval-gate" aria-label="Approval gate">
      {pending.stale ? (
        <p className="approval-gate__stale-banner" role="alert">
          This plan is stale: the project changed since it was proposed. Approval is refused —
          reject it and generate a fresh plan.
        </p>
      ) : null}

      <h2 className="select-none">Awaiting approval</h2>
      <p className="approval-gate__request">{pending.request}</p>

      <ul className="approval-gate__files" aria-label="Intended file changes">
        {pending.intent.files.map((file) => (
          <li key={file.path} className="approval-gate__file">
            <span className="approval-gate__op" data-operation={file.operation}>
              {OPERATION_LABELS[file.operation]}
            </span>
            <code>{file.path}</code>
          </li>
        ))}
      </ul>

      <div className="approval-gate__actions select-none">
        <button
          type="button"
          onClick={() => rejectAction.prepare({ token: pending.token })}
          disabled={rejectAction.phase === "preparing" || rejectAction.phase === "executing"}
        >
          Reject
        </button>
        <button
          type="button"
          onClick={() => approveAction.prepare({ token: pending.token })}
          disabled={
            pending.stale ||
            approveAction.phase === "preparing" ||
            approveAction.phase === "executing"
          }
        >
          Approve &amp; write code
        </button>
      </div>

      <ConfirmDialog action={approveAction} actionTitle="Approve plan and write code" />
      <ConfirmDialog action={rejectAction} actionTitle="Reject plan" />
    </section>
  );
}
