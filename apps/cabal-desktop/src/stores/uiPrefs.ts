// Zustand store for shell UI preferences (last module, sidebar collapsed), persisted across launches.
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UiPrefsState {
  lastModule: string | null;
  sidebarCollapsed: boolean;
}

interface UiPrefsActions {
  setLastModule: (moduleKey: string) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUiPrefsStore = create<UiPrefsState & UiPrefsActions>()(
  persist(
    (set) => ({
      lastModule: null,
      sidebarCollapsed: false,
      setLastModule: (moduleKey) => set({ lastModule: moduleKey }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
    }),
    { name: "cabal.uiPrefs" },
  ),
);
