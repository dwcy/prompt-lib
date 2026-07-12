// Module router: resolves the active module from the registry and renders it inside its own
// error boundary, falling back to the shared ModuleUnavailable placeholder pre-launch.
import { EmptyState } from "@/components/EmptyState";
import { ModuleErrorBoundary } from "@/components/shell/ModuleErrorBoundary";
import { ModuleUnavailable } from "@/modules/ModuleUnavailable";
import { findModule } from "@/modules/registry";

export interface ModuleOutletProps {
  activeModuleKey: string;
}

export function ModuleOutlet({ activeModuleKey }: ModuleOutletProps) {
  const module = findModule(activeModuleKey);
  if (module === undefined) {
    return (
      <EmptyState title="Unknown module" body={`No module registered for "${activeModuleKey}".`} />
    );
  }

  const ModuleComponent = module.component;
  return (
    <ModuleErrorBoundary key={module.key} moduleTitle={module.title}>
      {ModuleComponent !== null ? (
        <ModuleComponent />
      ) : (
        <ModuleUnavailable title={module.title} phase={module.phase} />
      )}
    </ModuleErrorBoundary>
  );
}
