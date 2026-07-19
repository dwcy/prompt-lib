// Console-style severity column labels shared by the collector log and incident ledger rows.
import type { DiagnosticEvent } from "@/api/schemas";

export const SEVERITY_LABELS: Record<DiagnosticEvent["severity"], string> = {
  info: "INFO",
  warning: "WARN",
  error: "ERR",
};
