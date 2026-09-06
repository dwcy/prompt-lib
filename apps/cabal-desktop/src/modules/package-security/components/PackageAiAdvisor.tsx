// Per-package "Ask AI" toggle + structured answer card: one-shot, unremembered CLI call per
// mount (no caching — the panel only mounts when a row expands, and each re-expand re-asks),
// rendered as a full-width row beneath the finding it answers.
import { useEffect } from "react";
import { type AdvisorPayload, useAskAboutPackage } from "@/api/securityEnvironment";
import { EmptyState } from "@/components/EmptyState";

export interface PackageAiAdvisorProps {
  findingKey: string;
  packageName: string;
}

const VERDICT_LABEL: Record<AdvisorPayload["verdict"], string> = {
  good: "Good",
  caution: "Caution",
  bad: "Bad",
};

export function PackageAiAdvisor({ findingKey, packageName }: PackageAiAdvisorProps) {
  const ask = useAskAboutPackage();
  const { mutate } = ask;

  useEffect(() => {
    mutate(findingKey);
  }, [findingKey, mutate]);

  return (
    <section className="pkgsec-advisor" aria-label={`AI opinion on ${packageName}`}>
      {ask.isPending || ask.isIdle ? (
        <EmptyState title={`Asking AI about ${packageName}…`} />
      ) : ask.isError ? (
        <EmptyState title="Could not reach the AI advisor" body={ask.error.message} />
      ) : ask.data.ok && ask.data.answer ? (
        <AdvisorCard
          model={ask.data.model}
          answer={ask.data.answer}
          onAskAgain={() => mutate(findingKey)}
        />
      ) : (
        <div className="pkgsec-advisor__failed">
          <div className="pkgsec-advisor__meta">
            <span>Advisor unavailable</span>
            <button type="button" onClick={() => mutate(findingKey)}>
              Ask again
            </button>
          </div>
          <p className="pkgsec-advisor__error">{ask.data?.error ?? "Unknown advisor error."}</p>
        </div>
      )}
    </section>
  );
}

interface AdvisorCardProps {
  model: string;
  answer: AdvisorPayload;
  onAskAgain: () => void;
}

function AdvisorCard({ model, answer, onAskAgain }: AdvisorCardProps) {
  return (
    <div className="pkgsec-advisor__card">
      <header className="pkgsec-advisor__head">
        <span className={`pkgsec-advisor__verdict pkgsec-advisor__verdict--${answer.verdict}`}>
          {VERDICT_LABEL[answer.verdict]}
        </span>
        <p className="pkgsec-advisor__summary">{answer.verdict_summary}</p>
        <div className="pkgsec-advisor__meta">
          <span>{model}</span>
          <button type="button" onClick={onAskAgain}>
            Ask again
          </button>
        </div>
      </header>

      {answer.warning ? (
        <div className="pkgsec-advisor__warning" role="alert">
          <span className="pkgsec-advisor__warning-badge">⚠ Risk</span>
          <span>{answer.warning}</span>
        </div>
      ) : null}

      <div className="pkgsec-advisor__section">
        <h4>What it solves</h4>
        <p>{answer.what_it_solves}</p>
      </div>

      <div className="pkgsec-advisor__section">
        <h4>Official docs &amp; description</h4>
        <p>{answer.official_docs.description}</p>
        {answer.official_docs.url ? (
          answer.official_docs.confident ? (
            <a
              className="pkgsec-advisor__docs-link"
              href={answer.official_docs.url}
              target="_blank"
              rel="noreferrer"
            >
              {answer.official_docs.url} ↗
            </a>
          ) : (
            <span className="pkgsec-advisor__docs-unconfident">
              ⚑ Unconfirmed link — verify before trusting: {answer.official_docs.url}
            </span>
          )
        ) : (
          <span className="pkgsec-advisor__docs-unconfident">
            ⚑ No confident official URL known
          </span>
        )}
      </div>

      <div className="pkgsec-advisor__section">
        <h4>Alternatives</h4>
        <ul className="pkgsec-advisor__alternatives">
          {answer.alternatives.map((alt) => (
            <li key={alt.name}>
              <span className="pkgsec-advisor__alt-name">{alt.name}</span>
              <span className="pkgsec-advisor__alt-reason">{alt.reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
