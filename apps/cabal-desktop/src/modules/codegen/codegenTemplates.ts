// The closed set of locked .NET architecture templates (018 data-model), shared by the
// change-request form (optional, first-run-only) and the new-service form (required).
export const CODEGEN_TEMPLATE_IDS = ["vertical-slice", "minimal-service", "clean-arch"] as const;

export type CodegenTemplateId = (typeof CODEGEN_TEMPLATE_IDS)[number];

export const CODEGEN_TEMPLATE_LABELS: Record<CodegenTemplateId, string> = {
  "vertical-slice": "Vertical slice",
  "minimal-service": "Minimal service",
  "clean-arch": "Clean architecture",
};
