// Git identity console: repo authorship hero, scope chain + identity editor, and the
// commit-policy blueprint (signature, vocabulary, protected branches, release authority).
import { useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import { queryKeys } from "@/api/queryKeys";
import {
  type GitIdentityRow,
  type GitIdentityScope,
  type GitPolicy,
  useGitIdentity,
  useGitPolicy,
} from "@/api/securityEnvironment";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EmptyState } from "@/components/EmptyState";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { useAction } from "@/hooks/useAction";
import "./GitIdentityModule.css";

export function GitIdentityModule() {
  const queryClient = useQueryClient();
  const identityQuery = useGitIdentity();
  const policyQuery = useGitPolicy();
  const [scope, setScope] = useState<GitIdentityScope>("global");
  const [identityDraft, setIdentityDraft] = useState({ name: "", email: "" });
  const [policyDraft, setPolicyDraft] = useState<PolicyDraft | null>(null);
  const identityAction = useAction("git.identity.set");
  const policyAction = useAction("git.policy.set");

  const selectedIdentity =
    identityQuery.data?.identities.find((identity) => identity.scope === scope) ?? null;

  useEffect(() => {
    if (selectedIdentity === null) return;
    setIdentityDraft({ name: selectedIdentity.name, email: selectedIdentity.email });
  }, [selectedIdentity]);

  useEffect(() => {
    if (policyQuery.data === undefined) return;
    setPolicyDraft(toDraft(policyQuery.data.policy));
  }, [policyQuery.data]);

  useEffect(() => {
    if (identityAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("gitIdentity") });
  }, [identityAction.phase, queryClient]);

  useEffect(() => {
    if (policyAction.phase !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.global("gitIdentity") });
  }, [policyAction.phase, queryClient]);

  const policyPayload = useMemo(
    () => (policyDraft === null ? null : fromDraft(policyDraft)),
    [policyDraft],
  );
  const policyValid =
    policyPayload !== null &&
    policyPayload.agent_name.length > 0 &&
    isPlausibleEmail(policyPayload.agent_email) &&
    policyPayload.allowed_types.length > 0 &&
    policyPayload.refuse_on_branches.length > 0;

  if (identityQuery.isPending || policyQuery.isPending) {
    return <EmptyState title="Loading git identity..." />;
  }
  if (identityQuery.isError) {
    return <EmptyState title="Git identity unavailable" body={identityQuery.error.message} />;
  }
  if (policyQuery.isError) {
    return <EmptyState title="Git policy unavailable" body={policyQuery.error.message} />;
  }
  if (policyDraft === null || policyPayload === null) {
    return <EmptyState title="Git policy did not load" />;
  }

  const effectiveIdentity = resolveEffectiveIdentity(identityQuery.data.identities);
  const identityDirty =
    selectedIdentity !== null &&
    (identityDraft.name.trim() !== selectedIdentity.name ||
      identityDraft.email.trim() !== selectedIdentity.email);
  const policyDirty = !samePolicy(policyPayload, policyQuery.data.policy);

  return (
    <div className="gid-workspace">
      <section className="gid-hero">
        <div className="gid-hero__intro">
          <span className="gid-eyebrow select-none">Source control trust</span>
          <h1>Authorship control</h1>
          <p>{identityQuery.data.repo_root ?? "No repository selected"}</p>
        </div>
        <div className="gid-hero__effective">
          <span className="gid-eyebrow">Effective author</span>
          <strong>{effectiveIdentity?.name || "Not configured"}</strong>
          <code>{effectiveIdentity?.email || "No email"}</code>
          <StatePill
            variant={effectiveIdentity === null ? "missing" : "ok"}
            label={effectiveIdentity?.scope ?? "none"}
          />
        </div>
        <div className="gid-hero__policy-source">
          <span className="gid-eyebrow">Policy source</span>
          <code>{policyQuery.data.source}</code>
        </div>
        <CardRefreshFooter>
          <RefreshButton
            label="git identity"
            onRefresh={() => {
              void identityQuery.refetch();
              void policyQuery.refetch();
            }}
            isFetching={identityQuery.isFetching || policyQuery.isFetching}
          />
        </CardRefreshFooter>
      </section>

      <section className="gid-authorship">
        <header className="gid-authorship__header">
          <div>
            <span className="gid-eyebrow">Resolution order</span>
            <h2>Authorship chain</h2>
          </div>
          <p>Project identity overrides the global baseline when configured.</p>
        </header>

        <div className="gid-authorship__chain">
          {identityQuery.data.identities.map((identity, index) => (
            <div className="gid-authorship__chain-segment" key={identity.scope}>
              {index > 0 ? (
                <span className="gid-authorship__connector" aria-hidden="true">
                  &gt;
                </span>
              ) : null}
              <IdentityScopeButton
                identity={identity}
                active={identity.scope === scope}
                effective={effectiveIdentity?.scope === identity.scope}
                onSelect={() => setScope(identity.scope)}
              />
            </div>
          ))}
        </div>

        <div className="gid-identity-editor">
          <div className="gid-identity-editor__avatar" aria-hidden="true">
            {identityInitial(identityDraft.name)}
          </div>
          <div className="gid-identity-editor__heading">
            <span className="gid-eyebrow select-none">{scope} scope</span>
            <h3>{scope === "global" ? "Global baseline" : "Project override"}</h3>
          </div>
          <label className="gid-field">
            <span>Name</span>
            <input
              value={identityDraft.name}
              onChange={(event) =>
                setIdentityDraft((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="gid-field">
            <span>Email</span>
            <input
              type="email"
              value={identityDraft.email}
              onChange={(event) =>
                setIdentityDraft((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>
          <button
            type="button"
            className="gid-identity-editor__save"
            disabled={
              selectedIdentity?.available !== true ||
              !identityDirty ||
              identityDraft.name.trim().length === 0 ||
              !isPlausibleEmail(identityDraft.email) ||
              identityAction.phase === "preparing"
            }
            onClick={() =>
              identityAction.prepare({
                scope,
                name: identityDraft.name.trim(),
                email: identityDraft.email.trim(),
              })
            }
          >
            Stage identity
          </button>
        </div>
      </section>

      <section className="gid-policy-editor">
        <header className="gid-policy-editor__header">
          <div>
            <span className="gid-eyebrow select-none">Commit policy</span>
            <h2>Agent guardrails</h2>
          </div>
          <div className="gid-policy-editor__actions">
            <StatePill variant={policyValid ? (policyDirty ? "update" : "ok") : "failed"} />
            <button
              type="button"
              disabled={!policyDirty}
              onClick={() => setPolicyDraft(toDraft(policyQuery.data.policy))}
            >
              Revert
            </button>
            <button
              type="button"
              onClick={() => setPolicyDraft(toDraft(policyQuery.data.defaults))}
            >
              Load defaults
            </button>
          </div>
        </header>

        <div className="gid-policy-blueprint">
          <section className="gid-policy-lane gid-policy-lane--signature">
            <header>
              <span>01</span>
              <div>
                <h3>Agent signature</h3>
                <p>Identity written to agent-authored commits.</p>
              </div>
            </header>
            <div className="gid-policy-form-grid">
              <label className="gid-field">
                <span>Agent name</span>
                <input
                  value={policyDraft.agentName}
                  onChange={(event) =>
                    setPolicyDraft((current) =>
                      current === null ? current : { ...current, agentName: event.target.value },
                    )
                  }
                />
              </label>
              <label className="gid-field">
                <span>Agent email</span>
                <input
                  type="email"
                  value={policyDraft.agentEmail}
                  onChange={(event) =>
                    setPolicyDraft((current) =>
                      current === null ? current : { ...current, agentEmail: event.target.value },
                    )
                  }
                />
              </label>
            </div>
          </section>

          <section className="gid-policy-lane gid-policy-lane--types">
            <header>
              <span>02</span>
              <div>
                <h3>Commit vocabulary</h3>
                <p>Allowed conventional commit prefixes.</p>
              </div>
            </header>
            <TokenListEditor
              label="Allowed commit types"
              values={policyDraft.allowedTypes}
              placeholder="Add type"
              onChange={(allowedTypes) =>
                setPolicyDraft((current) =>
                  current === null ? current : { ...current, allowedTypes },
                )
              }
            />
          </section>

          <section className="gid-policy-lane gid-policy-lane--branches">
            <header>
              <span>03</span>
              <div>
                <h3>Protected branches</h3>
                <p>Branches where agent commits are refused.</p>
              </div>
            </header>
            <TokenListEditor
              label="Refuse on branches"
              values={policyDraft.refuseOnBranches}
              placeholder="Add branch"
              onChange={(refuseOnBranches) =>
                setPolicyDraft((current) =>
                  current === null ? current : { ...current, refuseOnBranches },
                )
              }
            />
          </section>

          <section className="gid-policy-lane gid-policy-lane--delivery">
            <header>
              <span>04</span>
              <div>
                <h3>Release authority</h3>
                <p>Explicit controls for tags and remote delivery.</p>
              </div>
            </header>
            <div className="gid-policy-switches">
              <PolicySwitch
                label="Agent may tag"
                detail="Allow release tag creation"
                checked={policyDraft.agentMayTag}
                onChange={(agentMayTag) =>
                  setPolicyDraft((current) =>
                    current === null ? current : { ...current, agentMayTag },
                  )
                }
              />
              <PolicySwitch
                label="Auto push"
                detail="Push after a successful commit"
                checked={policyDraft.autoPush}
                onChange={(autoPush) =>
                  setPolicyDraft((current) =>
                    current === null ? current : { ...current, autoPush },
                  )
                }
              />
            </div>
          </section>
        </div>

        <footer className="gid-policy-editor__footer">
          <PolicyPreview policy={policyPayload} valid={policyValid} dirty={policyDirty} />
          <button
            type="button"
            disabled={!policyValid || !policyDirty || policyAction.phase === "preparing"}
            onClick={() => policyAction.prepare(policyPayload)}
          >
            Review policy change
          </button>
        </footer>
      </section>

      <ConfirmDialog action={identityAction} actionTitle="Set git identity" />
      <ConfirmDialog action={policyAction} actionTitle="Set git policy" />
    </div>
  );
}

interface PolicyDraft {
  agentName: string;
  agentEmail: string;
  allowedTypes: string[];
  refuseOnBranches: string[];
  agentMayTag: boolean;
  autoPush: boolean;
}

function IdentityScopeButton({
  identity,
  active,
  effective,
  onSelect,
}: {
  identity: GitIdentityRow;
  active: boolean;
  effective: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`gid-scope-card${active ? " is-active" : ""}`}
      onClick={onSelect}
      disabled={!identity.available}
    >
      <span className="gid-scope-card__scope">{identity.scope}</span>
      <span className="gid-scope-card__author">
        <strong>{identity.name || "Not configured"}</strong>
        <code>{identity.email || identity.source}</code>
      </span>
      <StatePill
        variant={effective ? "ok" : identity.email ? "unavailable" : "missing"}
        label={effective ? "effective" : identity.email ? "available" : "empty"}
      />
    </button>
  );
}

function TokenListEditor({
  label,
  values,
  placeholder,
  onChange,
}: {
  label: string;
  values: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [nextValue, setNextValue] = useState("");

  function addValue() {
    const value = nextValue.trim();
    if (value.length === 0 || values.includes(value)) {
      setNextValue("");
      return;
    }
    onChange([...values, value]);
    setNextValue("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter" && event.key !== ",") return;
    event.preventDefault();
    addValue();
  }

  return (
    <div className="gid-token-editor">
      <span className="visually-hidden">{label}</span>
      <div className="gid-token-editor__tokens">
        {values.map((value) => (
          <span key={value}>
            {value}
            <button
              type="button"
              aria-label={`Remove ${value}`}
              onClick={() => onChange(values.filter((item) => item !== value))}
            >
              x
            </button>
          </span>
        ))}
      </div>
      <div className="gid-token-editor__add">
        <input
          value={nextValue}
          onChange={(event) => setNextValue(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addValue}
          placeholder={placeholder}
          aria-label={placeholder}
        />
        <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={addValue}>
          Add
        </button>
      </div>
    </div>
  );
}

function PolicySwitch({
  label,
  detail,
  checked,
  onChange,
}: {
  label: string;
  detail: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="gid-policy-switch">
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </label>
  );
}

function PolicyPreview({
  policy,
  valid,
  dirty,
}: {
  policy: GitPolicy;
  valid: boolean;
  dirty: boolean;
}) {
  return (
    <div className="gid-policy-preview">
      <StatePill
        variant={valid ? (dirty ? "update" : "ok") : "failed"}
        label={!valid ? "invalid" : dirty ? "staged" : "active"}
      />
      <span>{policy.allowed_types.length} commit types</span>
      <span>{policy.refuse_on_branches.length} protected branches</span>
      <span>{policy.tags.agent_may_tag ? "tagging allowed" : "tagging blocked"}</span>
      <span>{policy.tags.auto_push ? "auto push" : "manual push"}</span>
    </div>
  );
}

function toDraft(policy: GitPolicy): PolicyDraft {
  return {
    agentName: policy.agent_name,
    agentEmail: policy.agent_email,
    allowedTypes: [...policy.allowed_types],
    refuseOnBranches: [...policy.refuse_on_branches],
    agentMayTag: policy.tags.agent_may_tag,
    autoPush: policy.tags.auto_push,
  };
}

function fromDraft(draft: PolicyDraft): GitPolicy {
  return {
    agent_name: draft.agentName.trim(),
    agent_email: draft.agentEmail.trim(),
    allowed_types: uniqueValues(draft.allowedTypes),
    refuse_on_branches: uniqueValues(draft.refuseOnBranches),
    tags: {
      agent_may_tag: draft.agentMayTag,
      auto_push: draft.autoPush,
    },
  };
}

function uniqueValues(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function samePolicy(left: GitPolicy, right: GitPolicy) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function resolveEffectiveIdentity(identities: GitIdentityRow[]) {
  const local = identities.find(
    (identity) => identity.scope === "local" && identity.available && identity.email,
  );
  return (
    local ?? identities.find((identity) => identity.scope === "global" && identity.email) ?? null
  );
}

function identityInitial(name: string) {
  return name.trim().charAt(0).toLocaleUpperCase() || "G";
}

function isPlausibleEmail(value: string) {
  const trimmed = value.trim();
  return (
    trimmed.includes("@") &&
    trimmed.indexOf("@") > 0 &&
    trimmed.lastIndexOf("@") < trimmed.length - 1
  );
}
