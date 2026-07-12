// Cross-module navigation: switches the shell's active module via the shared UI-prefs store, the
// same single source of truth App.tsx renders from — lets a module (e.g. Overview's deep links)
// switch modules without a prop drilled down from ModuleOutlet.
import type { ModuleKey } from "@/modules/registry";
import { useUiPrefsStore } from "@/stores/uiPrefs";

export interface UseModuleNavigationResult {
  navigateToModule: (moduleKey: ModuleKey) => void;
}

export function useModuleNavigation(): UseModuleNavigationResult {
  const setLastModule = useUiPrefsStore((state) => state.setLastModule);
  return { navigateToModule: setLastModule };
}
