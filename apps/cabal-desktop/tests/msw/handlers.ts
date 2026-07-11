// MSW request handlers shared across component tests.
// Empty for now — the envelope fixture library (backend envelope v2, ModuleHealth,
// Job, Ticket fixtures) lands in T026; handlers will be built on top of it there.
import type { HttpHandler } from "msw";

export const handlers: HttpHandler[] = [];
