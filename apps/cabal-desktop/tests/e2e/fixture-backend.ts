// Fixture backend launcher for Playwright e2e — documented deferral.
//
// T097 will implement this to spawn a real `cabal-backend` instance against a
// throwaway fixture project, wait for its handshake file, and return
// { port, token, close() } so specs can point the webview at a live backend
// without depending on a developer's local project state.
//
// Until then this stub throws so any spec that imports it fails loudly
// instead of silently no-op-ing.
export function launchFixtureBackend(): never {
  throw new Error("fixture backend lands with T097");
}
