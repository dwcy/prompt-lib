// The eye control and the three states an entry's retrievability puts it in.
//
// A `never` entry keeps a visible but permanently disabled control with a stated reason: the
// absence of a control reads as an oversight, while a disabled one with a reason teaches the
// constraint (FR-018). It is styled and labelled apart from a failed reveal, because one can
// never change and the other might (quickstart copy table).
import type { Retrievability, RevealStatus } from "@/api/envSources";

export interface RevealState {
  status: RevealStatus;
  value: string | null;
  reason: string | null;
  isReference: boolean;
}

export interface RevealCellProps {
  name: string;
  retrievability: Retrievability;
  retrievabilityReason: string | null;
  revealed: RevealState | null;
  isPending: boolean;
  onReveal: () => void;
  onMask: () => void;
}

export function RevealCell({
  name,
  retrievability,
  retrievabilityReason,
  revealed,
  isPending,
  onReveal,
  onMask,
}: RevealCellProps) {
  if (retrievability === "never") {
    return (
      <div className="env-reveal env-reveal--never">
        <button
          type="button"
          className="env-reveal__eye"
          disabled
          aria-label={`Value cannot be retrieved for ${name}`}
          title={retrievabilityReason ?? "This value can never be retrieved"}
        >
          <EyeOffIcon />
        </button>
        <span className="env-reveal__note">{retrievabilityReason ?? "not retrievable"}</span>
      </div>
    );
  }

  if (revealed !== null && revealed.status !== "revealed") {
    return (
      <div className="env-reveal env-reveal--refused" data-status={revealed.status}>
        <button
          type="button"
          className="env-reveal__eye"
          aria-label={`Try revealing ${name} again`}
          title="Try again"
          onClick={onReveal}
        >
          <EyeIcon />
        </button>
        <span className="env-reveal__note">
          {revealed.status === "denied" ? "Permission denied. " : ""}
          {revealed.reason ?? "The value could not be retrieved"}
        </span>
      </div>
    );
  }

  const isShown = revealed !== null && revealed.status === "revealed";
  return (
    <div className="env-reveal">
      <button
        type="button"
        className="env-reveal__eye"
        aria-label={isShown ? `Hide ${name}` : `Reveal ${name}`}
        aria-pressed={isShown}
        title={isShown ? "Hide value" : revealLabel(retrievability)}
        disabled={isPending}
        onClick={isShown ? onMask : onReveal}
      >
        {isShown ? <EyeOffIcon /> : <EyeIcon />}
      </button>
      {isShown ? (
        <ShownValue value={revealed.value} isReference={revealed.isReference} />
      ) : (
        // The bullets are a picture of "hidden", not text worth reading out, so the row of
        // glyphs carries the img role and the name states what is masked.
        <code className="env-reveal__masked" role="img" aria-label={`${name} is masked`}>
          {isPending ? "…" : "••••••••••••"}
        </code>
      )}
    </div>
  );
}

function ShownValue({ value, isReference }: { value: string | null; isReference: boolean }) {
  // An empty or whitespace-only value is a real answer and must not read as "unavailable".
  const isBlank = value === null || value.trim() === "";
  return (
    <span className="env-reveal__shown">
      {isReference ? (
        <span className="env-sources__badge" data-badge="reference">
          reference
        </span>
      ) : null}
      <code className={`env-reveal__value${isBlank ? " env-reveal__value--blank" : ""}`}>
        {isBlank ? (value === "" ? "(empty)" : "(blank)") : value}
      </code>
    </span>
  );
}

function revealLabel(retrievability: Retrievability): string {
  return retrievability === "permission_gated"
    ? "Reveal value — this may require additional access"
    : "Reveal value";
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.1 12s3.6-7 9.9-7 9.9 7 9.9 7-3.6 7-9.9 7-9.9-7-9.9-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m3 3 18 18" />
      <path d="M10.6 5.2A10.8 10.8 0 0 1 12 5c6.3 0 9.9 7 9.9 7a15.7 15.7 0 0 1-2.2 3.1M6.6 6.6C3.7 8.5 2.1 12 2.1 12s3.6 7 9.9 7c1.9 0 3.6-.6 5-1.5" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}
