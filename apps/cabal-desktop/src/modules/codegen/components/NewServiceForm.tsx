// New-service scaffold form: locked template pick + a destination confined to the selected
// project's directory (FR-011a), with a client-side escape/emptiness pre-check before submit —
// the backend's post-normalisation check in codegen.new_service remains the authority.
import { type FormEvent, useId, useMemo, useState } from "react";
import {
  CODEGEN_TEMPLATE_IDS,
  CODEGEN_TEMPLATE_LABELS,
  type CodegenTemplateId,
} from "@/modules/codegen/codegenTemplates";
import { resolveProjectRelativeDestination } from "@/modules/codegen/projectRelativeDestination";

export interface NewServiceFormValues {
  template: CodegenTemplateId;
  destination: string;
  description: string;
}

export interface NewServiceFormProps {
  projectPath: string | null;
  submitting: boolean;
  onSubmit: (values: NewServiceFormValues) => void;
}

export function NewServiceForm({ projectPath, submitting, onSubmit }: NewServiceFormProps) {
  const [template, setTemplate] = useState<CodegenTemplateId>(CODEGEN_TEMPLATE_IDS[0]);
  const [destinationInput, setDestinationInput] = useState("");
  const [description, setDescription] = useState("");
  const templateId = useId();
  const destinationId = useId();
  const descriptionId = useId();

  const destination = useMemo(
    () => resolveProjectRelativeDestination(destinationInput),
    [destinationInput],
  );
  const trimmedDescription = description.trim();
  const canSubmit = destination.normalized !== null && trimmedDescription.length > 0 && !submitting;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (destination.normalized === null || !canSubmit) return;
    onSubmit({ template, destination: destination.normalized, description: trimmedDescription });
  }

  return (
    <form className="codegen-new-service-form" onSubmit={handleSubmit}>
      <h2 className="select-none">Create a new service</h2>

      <label htmlFor={templateId} className="select-none">
        Template
      </label>
      <select
        id={templateId}
        value={template}
        onChange={(event) => setTemplate(event.currentTarget.value as CodegenTemplateId)}
        disabled={submitting}
      >
        {CODEGEN_TEMPLATE_IDS.map((id) => (
          <option key={id} value={id}>
            {CODEGEN_TEMPLATE_LABELS[id]}
          </option>
        ))}
      </select>

      <label htmlFor={destinationId} className="select-none">
        Destination (inside the selected project)
      </label>
      <input
        id={destinationId}
        type="text"
        value={destinationInput}
        onChange={(event) => setDestinationInput(event.currentTarget.value)}
        placeholder="services/orders-api"
        disabled={submitting}
      />
      {destination.error !== null ? (
        <p className="codegen-new-service-form__error" role="alert">
          {destination.error}
        </p>
      ) : (
        <p className="codegen-new-service-form__preview">
          Will scaffold into:{" "}
          <code>{formatDestinationPreview(projectPath, destination.normalized)}</code>
        </p>
      )}

      <label htmlFor={descriptionId} className="select-none">
        Description
      </label>
      <textarea
        id={descriptionId}
        value={description}
        onChange={(event) => setDescription(event.currentTarget.value)}
        placeholder="A minimal orders API with CRUD over orders…"
        rows={3}
        disabled={submitting}
      />

      <button type="submit" disabled={!canSubmit} className="select-none">
        {submitting ? "Scaffolding…" : "Scaffold service"}
      </button>
    </form>
  );
}

function formatDestinationPreview(projectPath: string | null, normalized: string | null): string {
  if (normalized === null) return "";
  if (projectPath === null) return normalized;
  return `${projectPath}/${normalized}`;
}
