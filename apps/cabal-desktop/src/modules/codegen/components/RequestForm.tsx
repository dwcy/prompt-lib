// Prose change-request form: describe what to build or change against the selected project,
// with an optional first-time template pick (ignored once the project's template is locked).
import { type FormEvent, useId, useState } from "react";
import {
  CODEGEN_TEMPLATE_IDS,
  CODEGEN_TEMPLATE_LABELS,
  type CodegenTemplateId,
} from "@/modules/codegen/codegenTemplates";

export interface RequestFormValues {
  request: string;
  template?: CodegenTemplateId;
}

export interface RequestFormProps {
  submitting: boolean;
  onSubmit: (values: RequestFormValues) => void;
}

export function RequestForm({ submitting, onSubmit }: RequestFormProps) {
  const [request, setRequest] = useState("");
  const [template, setTemplate] = useState<CodegenTemplateId | "">("");
  const requestId = useId();
  const templateId = useId();

  const trimmedRequest = request.trim();
  const canSubmit = trimmedRequest.length > 0 && !submitting;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({ request: trimmedRequest, template: template === "" ? undefined : template });
  }

  return (
    <form className="codegen-request-form" onSubmit={handleSubmit}>
      <h2 className="select-none">Describe a change</h2>
      <label htmlFor={requestId} className="select-none">
        What should be built or changed?
      </label>
      <textarea
        id={requestId}
        value={request}
        onChange={(event) => setRequest(event.currentTarget.value)}
        placeholder="Add a webhook receiver endpoint that validates the signature header…"
        rows={4}
        disabled={submitting}
      />
      <label htmlFor={templateId} className="select-none">
        Template (only used the first time this project generates)
      </label>
      <select
        id={templateId}
        value={template}
        onChange={(event) => setTemplate(event.currentTarget.value as CodegenTemplateId | "")}
        disabled={submitting}
      >
        <option value="">Use the project's locked template</option>
        {CODEGEN_TEMPLATE_IDS.map((id) => (
          <option key={id} value={id}>
            {CODEGEN_TEMPLATE_LABELS[id]}
          </option>
        ))}
      </select>
      <button type="submit" disabled={!canSubmit} className="select-none">
        {submitting ? "Generating plan…" : "Generate plan"}
      </button>
    </form>
  );
}
