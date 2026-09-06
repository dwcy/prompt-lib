// Scope-removal picker shown before disabling a connector that lives in more than one
// configuration layer (removable_scopes.length > 1) — same confirm-flow-gated disable action,
// restyled as a console dialog with divider rows per removable/retained scope.
import type { McpServer } from "@/api/operations";
import { StatePill } from "@/components/StatePill";
import { scopeImpactCopy } from "@/modules/mcp/mcpStatus";

export interface McpScopeDialogProps {
  candidate: McpServer;
  onRemoveScope: (server: McpServer, scope: string) => void;
  onDismiss: () => void;
}

export function McpScopeDialog({ candidate, onRemoveScope, onDismiss }: McpScopeDialogProps) {
  return (
    <div
      className="mcp-scope-dialog-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mcp-scope-dialog-title"
    >
      <section className="mcp-scope-dialog">
        <header>
          <div>
            <span className="mcp-eyebrow">Connector ownership</span>
            <h2 id="mcp-scope-dialog-title">Remove one {candidate.name} scope</h2>
            <p>
              The connector can exist in several configuration layers. Removing one layer leaves
              every other owner intact.
            </p>
          </div>
          <StatePill variant="degraded" label={`${candidate.scopes.length} scopes`} />
        </header>

        <div className="mcp-scope-dialog__rows">
          {candidate.scopes.map((item, index) => {
            const removable = candidate.removable_scopes.includes(item);
            return (
              <div key={item} className={removable ? "is-removable" : "is-retained"}>
                <span className="mcp-scope-dialog__step">{String(index + 1).padStart(2, "0")}</span>
                <span className="mcp-scope-dialog__identity">
                  <strong>{item}</strong>
                  <small>{scopeImpactCopy(item)}</small>
                </span>
                <StatePill
                  variant={removable ? "degraded" : "ok"}
                  label={removable ? "removable" : "retained"}
                />
                {removable ? (
                  <button
                    type="button"
                    className="mcp-scope-dialog__remove"
                    onClick={() => onRemoveScope(candidate, item)}
                  >
                    Remove this scope
                  </button>
                ) : (
                  <span className="mcp-scope-dialog__locked">Managed elsewhere</span>
                )}
              </div>
            );
          })}
        </div>

        <footer>
          <span>
            A prepared confirmation will show the exact configuration file changed by the selected
            ownership layer.
          </span>
          <button type="button" onClick={onDismiss}>
            Keep all scopes
          </button>
        </footer>
      </section>
    </div>
  );
}
