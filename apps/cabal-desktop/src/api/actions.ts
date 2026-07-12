// Raw prepare/execute callers for the action-safety protocol (the only mutation path).
import { z } from "zod";
import { apiPost, requireData } from "@/api/client";
import { type ConfirmationTicket, confirmationTicketSchema } from "@/api/schemas";

const executeResultSchema = z.record(z.string(), z.unknown());

export interface ExecuteActionResult {
  jobId: string | null;
  data: Record<string, unknown> | null;
}

export async function prepareAction(
  actionId: string,
  params: Record<string, unknown>,
): Promise<ConfirmationTicket> {
  const envelope = await apiPost(
    `/api/actions/${actionId}/prepare`,
    confirmationTicketSchema,
    params,
  );
  return requireData(envelope, `prepare ${actionId}`);
}

export async function executeAction(
  actionId: string,
  ticketId: string,
): Promise<ExecuteActionResult> {
  const envelope = await apiPost(`/api/actions/${actionId}/execute`, executeResultSchema, {
    ticket_id: ticketId,
  });
  const data = requireData(envelope, `execute ${actionId}`);
  const jobIdValue = data.job_id;
  return {
    jobId: typeof jobIdValue === "string" ? jobIdValue : null,
    data,
  };
}
