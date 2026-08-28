import "@/styles/globals.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "@/App";
import { queryClient } from "@/api/queryClient";
import { ensureRuntimeConfig } from "@/lib/runtimeConfig";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Root element #root not found");
}

const root = createRoot(rootElement);

function mount() {
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
}

// In the desktop shell the backend port and token must be in hand before the first
// request; a reloaded page starts without them until the shell answers.
ensureRuntimeConfig().then(mount, (error: unknown) => {
  console.error("cabal-desktop: backend connection unavailable", error);
  mount();
});
