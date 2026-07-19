// Generic prepare -> confirm -> execute flow for the action-safety protocol, with job-tray tracking.
import { useMutation } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { type ExecuteActionResult, executeAction, prepareAction } from "@/api/actions";
import type { ApiError } from "@/api/errors";
import type { ConfirmationTicket } from "@/api/schemas";
import { useJobTrayStore } from "@/stores/jobTray";

export type ActionPhase = "idle" | "preparing" | "ready" | "executing" | "succeeded" | "error";

export interface UseActionResult {
  phase: ActionPhase;
  ticket: ConfirmationTicket | null;
  error: ApiError | null;
  reviewNotice: boolean;
  jobId: string | null;
  prepare: (params: Record<string, unknown>) => void;
  confirm: () => void;
  reset: () => void;
}

export function useAction(actionId: string): UseActionResult {
  const [phase, setPhase] = useState<ActionPhase>("idle");
  const [ticket, setTicket] = useState<ConfirmationTicket | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [reviewNotice, setReviewNotice] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pendingParams, setPendingParams] = useState<Record<string, unknown>>({});
  const addJob = useJobTrayStore((state) => state.addJob);

  const prepareMutation = useMutation<ConfirmationTicket, ApiError, Record<string, unknown>>({
    mutationFn: (params) => prepareAction(actionId, params),
    onSuccess: (nextTicket) => {
      setTicket(nextTicket);
      setPhase("ready");
    },
    onError: (nextError) => {
      setError(nextError);
      setPhase("error");
    },
  });

  const executeMutation = useMutation<ExecuteActionResult, ApiError, string>({
    mutationFn: (ticketId) => executeAction(actionId, ticketId),
    onSuccess: (result) => {
      setReviewNotice(false);
      if (result.jobId !== null) {
        addJob(result.jobId);
        setJobId(result.jobId);
      }
      setPhase("succeeded");
    },
    onError: (nextError) => {
      if (nextError.code === "state_changed") {
        // FR-014 re-review flow: the ticket was invalidated by precondition drift —
        // re-prepare automatically so the confirm dialog re-renders the fresh preview.
        setReviewNotice(true);
        setPhase("preparing");
        prepareMutation.mutate(pendingParams);
        return;
      }
      setError(nextError);
      setPhase("error");
    },
  });

  const prepare = useCallback(
    (params: Record<string, unknown>) => {
      setError(null);
      setReviewNotice(false);
      setPendingParams(params);
      setPhase("preparing");
      prepareMutation.mutate(params);
    },
    [prepareMutation],
  );

  const confirm = useCallback(() => {
    if (ticket === null) return;
    setPhase("executing");
    executeMutation.mutate(ticket.ticket_id);
  }, [ticket, executeMutation]);

  const reset = useCallback(() => {
    setPhase("idle");
    setTicket(null);
    setError(null);
    setReviewNotice(false);
    setJobId(null);
  }, []);

  return { phase, ticket, error, reviewNotice, jobId, prepare, confirm, reset };
}
